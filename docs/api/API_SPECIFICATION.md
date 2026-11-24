# API_SPECIFICATION.md — Enterprise Infrastructure Intelligence

> Version : spécification V3 §16. Statut : PHASE 0 — contrats définis,
> aucune route métier implémentée (squelette : `/health`, `/api/v1/health`).

## 1. Principes

- REST, versionnée : base **`/api/v1`** (toute évolution préserve la
  compatibilité ou fait l'objet d'une migration documentée).
- Documentation OpenAPI générée par FastAPI (`/docs`, `/openapi.json`).
- Authentification : OIDC (Bearer JWT) ; autorisation RBAC vérifiée
  **côté serveur** sur chaque route ; aucune donnée hors organisation
  autorisée.
- Toutes les réponses sont en JSON ; dates en ISO 8601 UTC.
- Les opérations longues sont asynchrones et retournent un identifiant
  de tâche consultable (`GET /api/v1/tasks/{task_id}`).

## 2. Conventions

### 2.1 Enveloppe de réponse

Succès (objet unique) :

```json
{ "data": { "...": "..." }, "meta": { "request_id": "req_..." } }
```

Succès (liste paginée) :

```json
{
  "data": [ "..." ],
  "meta": { "request_id": "req_...", "page": 1, "per_page": 50, "total": 128 }
}
```

Erreur :

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Resource not found.",
    "details": { "resource": "connector", "id": "..." },
    "request_id": "req_..."
  }
}
```

### 2.2 Codes HTTP et erreurs

| Code | Usage |
|---|---|
| 200 | Lecture / mise à jour réussie |
| 201 | Création réussie |
| 202 | Accepté (traitement asynchrone) |
| 204 | Suppression réussie (sans corps) |
| 400 | Validation (détails par champ, format Zod/Pydantic) |
| 401 | Non authentifié |
| 403 | Non autorisé (permission / organisation) |
| 404 | Ressource introuvable |
| 409 | Conflit (ex. unicité) |
| 422 | Entité non traitable (règle métier) |
| 429 | Limite de débit atteinte |
| 500 | Erreur interne (jamais de stack trace ni de secret exposé) |

Codes d'erreur stables (`VALIDATION_ERROR`, `UNAUTHORIZED`, `FORBIDDEN`,
`NOT_FOUND`, `CONFLICT`, `RATE_LIMITED`, `INTERNAL_ERROR`, …).

### 2.3 Pagination, filtres, tri, recherche

- Pagination : `?page=1&per_page=50` (défaut 50, max 200).
- Tri : `?sort=-created_at` (`-` = descendant).
- Filtres : `?status=active&organization_id=...` (l'organisation est
  toujours imposée côté serveur à partir du token).
- Recherche : `?q=...` (recherche plein texte sur les champs indexés).

### 2.4 Idempotence et débit

- Les créations sensibles acceptent `Idempotency-Key` (header).
- Limitation de débit par organisation et par utilisateur (429 + header
  `Retry-After`).
- Validation stricte des entrées (Pydantic) ; rejet des champs inconnus
  non déclarés.

## 3. Ressources (aperçu `/api/v1`)

| Groupe | Routes principales |
|---|---|
| Auth | `POST /auth/login` (OIDC), `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me` |
| Organizations | `GET/POST /organizations`, `GET/PATCH/DELETE /organizations/{id}` |
| Users & roles | `GET/POST /organizations/{id}/members`, `GET/POST /roles`, `GET /permissions` |
| Sites | `GET/POST /organizations/{id}/sites` |
| Infrastructure | `GET /organizations/{id}/resources`, `GET /resources/{id}`, `GET /resources/{id}/history` |
| Connectors | `GET/POST /organizations/{id}/connectors`, `POST /connectors/{id}/verify`, `POST /connectors/{id}/sync`, `GET /connectors/{id}/sync-runs` |
| Monitoring | `GET /resources/{id}/metrics?from=&to=&metric=`, `GET /organizations/{id}/health` |
| Alerts | `GET/POST /organizations/{id}/alert-rules`, `GET /organizations/{id}/alerts`, `POST /alerts/{id}/ack`, `POST /alerts/{id}/assign` |
| Incidents | `GET/POST /organizations/{id}/incidents`, `PATCH /incidents/{id}`, `POST /incidents/{id}/events` |
| Automation | `GET/POST /organizations/{id}/workflows`, `POST /workflows/{id}/simulate`, `POST /workflows/{id}/execute`, `GET /workflow-runs/{id}` |
| AI | `POST /organizations/{id}/ai/ask`, `GET /organizations/{id}/ai/recommendations` |
| Costs | `GET /organizations/{id}/costs?from=&to=`, `GET /organizations/{id}/costs/underused` |
| Reports | `GET/POST /organizations/{id}/reports`, `GET /reports/{id}/download` |
| Audit | `GET /organizations/{id}/audit-logs` |
| Admin SaaS | `GET /admin/organizations`, `GET /admin/usage` (rôle plateforme uniquement) |

Chaque route : permissions requises documentées dans l'OpenAPI
(`x-permissions`), tests d'autorisation obligatoires.

## 4. Connecteurs (Data Plane → Control Plane)

Les connecteurs n'appellent pas l'API publique : ils utilisent les
endpoints dédiés mTLS (`/api/v1/connectors/ingest`, `/sync`, `/events`,
`/metrics`) avec identité de connecteur et versionnement de protocole.
Voir `docs/api/CONNECTOR_SPECIFICATION.md`.

## 5. Versionnement et dépréciation

- `/api/v1` stable ; toute rupture → `/api/v2` + guide de migration.
- En-têtes de dépréciation (`Deprecation`, `Sunset`) quand applicable.
- Rétrocompatibilité des champs : ajout autorisé, suppression interdite
  sans version majeure.
