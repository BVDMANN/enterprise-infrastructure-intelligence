# DATABASE_DESIGN.md — Enterprise Infrastructure Intelligence

> Version : spécification V3 §8. Statut : schéma livré progressivement par migrations Alembic jusqu'à 0004 ; RBAC 0005 en revue dans PR #17. ORM : SQLAlchemy 2.
> Base métier : PostgreSQL 16. Les métriques ne sont PAS stockées
> indéfiniment dans PostgreSQL (VictoriaMetrics).

## 1. Principes

- **Multi-tenancy dès le départ** : chaque ligne métier porte
  `organization_id` ; toute requête est limitée à l'organisation
  autorisée. Évaluation de PostgreSQL Row-Level Security (RLS) en
  complément de l'autorisation applicative (ADR-0005) — jamais de
  filtre reposant uniquement sur le frontend.
- Clés primaires : UUID (`gen_random_uuid()`), sauf tables de liaison
  (clé composite).
- Toutes les tables : `created_at`, `updated_at` (UTC, `timestamptz`).
- Suppression logique (`deleted_at`) pour les entités métier sensibles
  (organisations, utilisateurs, ressources, connecteurs).
- Contraintes d'unicité explicites ; index sur toutes les clés
  étrangères et les colonnes de recherche/filtrage.
- Aucun secret en clair : les credentials de connecteurs sont chiffrés
  (référence vers un gestionnaire de secrets, ex. Vault) — jamais de
  mot de passe/token en base en clair.

## 2. Entités principales (spécification §8)

### 2.1 Identité et organisation

| Table | Colonnes clés | Contraintes / index |
|---|---|---|
| `organizations` | `id` UUID PK, `name`, `slug` unique, `plan_id` FK, `deleted_at` | `slug` unique ; index `plan_id` |
| `users` | `id` UUID PK, `email` unique (citext), `display_name`, `oidc_subject` unique, `mfa_enabled`, `is_active` | `email` unique ; index `oidc_subject` |
| `memberships` | `id` PK, `organization_id` FK, `user_id` FK, `role_id` FK composite avec `organization_id`, `created_at` | unique (`organization_id`, `user_id`) ; rôle limité au même tenant |
| `roles` | `id` PK, `organization_id` FK NOT NULL, `name`, `is_system` | unique (`organization_id`, `name`) et (`organization_id`, `id`) ; rôles plateforme globaux différés |
| `permissions` | `id` PK, `name` unique (ex. `infrastructure.read`), `description` | `name` unique |
| `role_permissions` | `role_id` FK, `permission_id` FK | PK composite ; suppression en cascade des liens |
| `sessions` | `id` PK, `user_id` FK, `token_hash`, `expires_at`, `revoked_at`, `ip`, `user_agent` | index `user_id`, `expires_at` |

### 2.2 Inventaire

| Table | Colonnes clés | Contraintes / index |
|---|---|---|
| `sites` | `id` PK, `organization_id` FK, `name`, `location`, `timezone` | index `organization_id` |
| `infrastructure_nodes` | `id` PK, `organization_id` FK, `site_id` FK, `connector_id` FK, `external_id`, `kind` (host/vm/container/cluster…), `name`, `status`, `last_seen_at` | unique (`connector_id`, `external_id`) ; index `organization_id`, `status` |
| `infrastructure_resources` | `id` PK, `organization_id` FK, `node_id` FK, `kind` (cpu/ram/disk/network/service…), `name`, `capacity`, `status`, `last_sync_at` | index `organization_id`, `node_id` |
| `resource_relationships` | `id` PK, `organization_id` FK, `source_id` FK, `target_id` FK, `relation_type` | index `source_id`, `target_id` |
| `connectors` | `id` PK, `organization_id` FK, `type` (proxmox/debian/aws/simulation), `name`, `status`, `version`, `last_seen_at` | index `organization_id`, `status` |
| `connector_identities` | `id` PK, `connector_id` FK unique, `certificate_fingerprint`, `issued_at`, `expires_at`, `revoked_at` | unique `connector_id` |
| `connector_credentials` | `id` PK, `connector_id` FK, `secret_ref` (référence Vault, **jamais la valeur**), `scope`, `expires_at` | index `connector_id` |
| `connector_sync_runs` | `id` PK, `connector_id` FK, `started_at`, `finished_at`, `status`, `resources_seen`, `resources_added`, `resources_removed`, `error` | index `connector_id`, `started_at` |

### 2.3 Supervision, alertes, incidents

| Table | Colonnes clés | Contraintes / index |
|---|---|---|
| `metrics_metadata` | `id` PK, `organization_id` FK, `resource_id` FK, `metric_name`, `unit`, `retention_days` | unique (`resource_id`, `metric_name`) |
| `alert_rules` | `id` PK, `organization_id` FK, `name`, `metric`, `operator`, `threshold`, `duration_s`, `severity`, `is_active` | index `organization_id` |
| `alerts` | `id` PK, `organization_id` FK, `rule_id` FK, `resource_id` FK, `severity`, `state` (firing/acked/resolved), `started_at`, `resolved_at`, `dedup_key` | unique `dedup_key` (actif) ; index `organization_id`, `state` |
| `incidents` | `id` PK, `organization_id` FK, `title`, `severity`, `state` (new/in_progress/waiting/resolved/closed), `assignee_id` FK, `resource_id` FK, `root_cause`, `closed_at` | index `organization_id`, `state` |
| `incident_events` | `id` PK, `incident_id` FK, `actor_id` FK, `event_type`, `comment`, `created_at` | index `incident_id` |

### 2.4 Automatisation et IA

| Table | Colonnes clés |
|---|---|
| `workflows` | `id` PK, `organization_id` FK, `name`, `owner_id` FK, `current_version_id` FK, `is_active` |
| `workflow_versions` | `id` PK, `workflow_id` FK, `version`, `definition` (JSONB validé), `created_at` |
| `workflow_runs` | `id` PK, `workflow_id` FK, `version`, `trigger`, `status`, `started_at`, `finished_at`, `result` (JSONB) |
| `approval_requests` | `id` PK, `organization_id` FK, `workflow_run_id` FK, `requested_by` FK, `approver_id` FK, `state`, `decided_at` |
| `automation_actions` | `id` PK, `organization_id` FK, `workflow_run_id` FK, `action_type`, `target_resource_id` FK, `status`, `verified_at` |
| `ai_interactions` | `id` PK, `organization_id` FK, `user_id` FK, `kind` (analyst/incident/cost/optimization/security/automation), `prompt_version`, `input_ref`, `output_ref`, `created_at` |
| `ai_recommendations` | `id` PK, `organization_id` FK, `interaction_id` FK, `kind`, `content`, `state` (proposed/accepted/rejected/executed), `policy_check` (JSONB) |

### 2.5 Rapports, audit, facturation

| Table | Colonnes clés |
|---|---|
| `reports` | `id` PK, `organization_id` FK, `type`, `period_start`, `period_end`, `generated_at`, `format`, `storage_ref`, `limitations` (texte) |
| `notifications` | `id` PK, `organization_id` FK, `user_id` FK, `channel`, `kind`, `payload` (JSONB), `sent_at`, `read_at` |
| `audit_logs` | `id` PK, `organization_id` FK (nullable = plateforme), `actor_id` FK, `action`, `resource_type`, `resource_id`, `details` (JSONB, **sans secret**), `created_at` — **append-only** |
| `plans` | `id` PK, `name` unique (Business/Professional/Enterprise/Strategic), `limits` (JSONB), `is_active` |
| `subscriptions` | `id` PK, `organization_id` FK, `plan_id` FK, `state`, `started_at`, `renews_at`, `cancelled_at` |
| `invoices` | `id` PK, `organization_id` FK, `subscription_id` FK, `amount`, `currency`, `state`, `issued_at`, `paid_at` |
| `usage_records` | `id` PK, `organization_id` FK, `metric` (resources/connectors/users…), `value`, `period` |

## 3. Règles de modélisation

- **Relations** : FK avec `ON DELETE RESTRICT` par défaut pour les
  entités métier ; `CASCADE` uniquement pour les lignes dépendantes
  (ex. `incident_events`).
- **JSONB** : réservé aux définitions versionnées et aux détails
  d'audit ; jamais pour des données requêtées en filtre principal.
- **Rétention** : `metrics_metadata.retention_days` pilote la
  conservation ; les métriques brutes vivent dans VictoriaMetrics,
  pas dans PostgreSQL.
- **Audit** : `audit_logs` est append-only (pas d'UPDATE/DELETE
  applicatif) ; horodatage et identité systématiques.
- **RLS** : à évaluer en PHASE 1 (ADR-0005) : politiques par
  `organization_id` en complément des vérifications applicatives.
- **Tests** : tests de migration, tests d'isolation multi-tenant
  obligatoires avant ACCEPTED.


### État RBAC P1-A3 (PR #17, brouillon)

Le schéma cible est désormais matérialisé dans la branche P1-A3 : roles.organization_id est obligatoire, et la clé étrangère composite des memberships empêche au niveau PostgreSQL/SQLite d'affecter un rôle d'une organisation à une autre. Le catalogue de permissions est global (noms stables), mais chaque rôle est tenant-scoped. Les rôles de plateforme sont différés jusqu'à la création d'une frontière d'administration plateforme dédiée. La migration 0005 reprend les anciens rôles texte et refuse un downgrade qui supprimerait des rôles personnalisés ou une matrice de permissions modifiée.


### Validation PostgreSQL du lot RBAC — run #134 (26/11/2026)

Le smoke CI a testé une base avec un ancien membership owner sous la révision 0004 : après upgrade 0005, le membership référence un rôle owner de la même organisation et ce rôle porte 9 permissions. Une insertion de membership avec le role_id d'une autre organisation est rejetée par fk_memberships_organization_role. Le downgrade 0005 restaure le rôle texte owner ; les fixtures CI sont supprimées, puis downgrade base et nouvel upgrade head réussissent. Ce résultat valide la migration et la contrainte composite sur PostgreSQL dans l'environnement CI ; il ne constitue pas une validation RLS complète ni une validation locale.
