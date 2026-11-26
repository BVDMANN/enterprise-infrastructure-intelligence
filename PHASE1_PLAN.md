# PHASE1_PLAN.md — Enterprise Infrastructure Intelligence

> Version : 1.0 — 25 novembre 2026
> Branche de préparation : `audit/phase-0-followup`
> Statut : plan préparé ; aucun endpoint métier ni accès infrastructure réelle ajouté.

## 1. Objectif de Phase 1

Livrer un premier socle SaaS multi-tenant réellement testable : identité, organisations, rôles, isolation des données et traçabilité. Le dashboard, l'inventaire et les connecteurs réels ne commencent qu'après validation de ce socle.

Principes non négociables :

- Aucun endpoint métier accessible sans authentification et autorisation serveur.
- Chaque donnée métier tenantée porte un `organization_id` ; le tenant est déterminé côté serveur, jamais depuis une valeur frontend seule.
- Les tests d'accès inter-tenant sont bloquants en CI.
- Les connecteurs restent simulés ou strictement lecture seule ; aucune infrastructure réelle ni aucun secret réel pendant cette phase.
- Les recommandations IA ne peuvent pas exécuter de commande ; les actions sensibles restent soumises à une politique déterministe et à une validation humaine.
- Les migrations sont la source de vérité du schéma ; pas de `Base.metadata.create_all()` en production ou au démarrage applicatif.

## 2. Préconditions et portes de sortie

| Porte | Critère | État au 25/11 |
|---|---|---|
| G0 — CI/Compose | Build des 4 images, configuration Compose et smoke test complets | TESTED — run #54 |
| G1 — Ports locaux | DB/Redis/API/Web publiés uniquement sur 127.0.0.1 ; assertion CI | TESTED — run #54 |
| G2 — Runtime Web | Node 22 sur Docker et CI ; lint, typecheck, build et smoke | TESTED — run #54 |
| G3 — Audit dépendances | Résultats actuels documentés, job explicitement report-only | TESTED / REPORT-ONLY — vulnérabilités encore ouvertes |
| G4 — Poste développeur | `docker compose up --build` validé sur le poste local | À confirmer localement |

G0–G3 sont validées par la CI hébergée. G4 reste une vérification locale, mais ne doit pas conduire à brancher un environnement réel. Les vulnérabilités Starlette/Pytest et npm sont suivies dans `docs/security/SECURITY_AUDIT_2026-11-25.md` ; toute montée de version est un lot isolé avec tests.

## 3. Découpage P1-A — fondations sécurité et données

Les sous-lots sont courts, empilés dans l'ordre et chacun possède ses propres critères d'acceptation.

### P1-A0 — Fondation Alembic et migrations

**But :** rendre les migrations déterministes et testables avant d'ajouter les entités métier.

Travail :
- vérifier la configuration Alembic et le chargement de `Base.metadata` ;
- créer la première révision contrôlée (extensions PostgreSQL nécessaires, notamment `citext` si retenue) ;
- documenter la stratégie upgrade/downgrade et le traitement des migrations déjà appliquées ;
- ajouter un test PostgreSQL 16 en CI : base vide → `alembic upgrade head` → `alembic current` → downgrade contrôlé → upgrade à nouveau ;
- interdire `Base.metadata.create_all()` dans le chemin de démarrage applicatif.

Acceptation :
- aucune URL ou credential réel dans les fichiers ;
- migration reproductible sur PostgreSQL 16 vierge ;
- état Alembic exactement à `head` après upgrade ;
- tests d'upgrade/downgrade verts ;
- aucun changement destructif appliqué à une base existante.

### P1-A1 — Organisations, utilisateurs et memberships

**But :** poser les entités de tenant sans ouvrir encore de routes publiques.

Modèle :
- `organizations` : UUID, nom, slug unique, timestamps, soft delete ;
- `users` : UUID, email normalisé/unique, display_name, subject OIDC unique, statut actif ;
- `memberships` : organisation + utilisateur + rôle, unicité (organization_id, user_id).

Tests :
- contraintes d'unicité slug/email/membership ;
- utilisateur sans membership ne voit aucune donnée d'organisation ;
- impossible de rattacher un membership à une organisation inexistante ;
- suppression logique et intégrité référentielle.

### P1-A2 — Sessions et OIDC

**But :** authentifier les utilisateurs sans implémenter un fournisseur propriétaire.

Travail :
- interface OIDC provider indépendante du fournisseur ;
- validation stricte issuer, audience, signature, nonce, state et expiration ;
- sessions serveur avec token opaque, hashé en base, expiration et révocation ;
- cookies Secure, HttpOnly, SameSite adaptés ; CSRF et vérification Origin pour les mutations ;
- aucune conservation de bearer token brut en base ou dans les logs.

Tests négatifs :
- issuer/audience incorrects ;
- signature invalide ;
- nonce/state manquant ou incorrect ;
- token expiré ;
- session expirée ou révoquée ;
- cookie absent ou CSRF invalide.

### P1-A3 — RBAC

**But :** appliquer les permissions côté API, jamais uniquement dans l'interface.

Modèle :
- rôles globaux ou propres à une organisation ;
- permissions nommées et table de liaison role_permissions ;
- rôle effectif résolu à partir du membership actif.

Tests négatifs :
- membre lecteur ne peut pas modifier ;
- membre sans permission ne peut pas appeler l'action ;
- rôle d'une organisation A non réutilisable dans B ;
- tentative d'élévation de rôle refusée et journalisée.

### P1-A4 — Isolation multi-tenant

**But :** empêcher une fuite inter-organisation même en cas d'erreur de filtre applicatif.

Travail :
- `organization_id` obligatoire sur chaque table métier tenantée ;
- contexte tenant dérivé de la session et du membership ;
- dépôts/repositories filtrés côté serveur ;
- décision RLS documentée dans ADR-0005 avant activation ;
- si RLS activée, tests avec un rôle PostgreSQL non-superuser (les superusers contournent RLS).

Tests négatifs bloquants :
- lecture d'un ID appartenant à une autre organisation → 404/403 ;
- mutation avec un organization_id forgé → rejet ;
- listes, exports et relations ne retournent aucune donnée d'un autre tenant ;
- tests parallèles de deux tenants sans contamination de contexte.

### P1-A5 — Audit log

**But :** tracer les actions sensibles sans enregistrer de secrets.

Champs minimaux : actor_id, organization_id, action, target_type, target_id, outcome, request_id, timestamp, métadonnées filtrées.

Tests :
- écriture append-only via le service dédié ;
- refus de modification/suppression par les rôles applicatifs ;
- absence de token, mot de passe, secret ou contenu sensible dans les événements ;
- tenant et acteur issus du contexte serveur.

## 4. Ordre et dépendances

```text
P1-A0 Alembic
   |
P1-A1 Organisations / users / memberships
   |
P1-A2 OIDC / sessions
   |
P1-A3 RBAC
   |
P1-A4 Isolation multi-tenant
   |
P1-A5 Audit log
   |
P1-B Dashboard / inventaire / simulation intégrée
   |
P1-C Connecteurs Proxmox et Debian en lecture seule
   |
P1-D Métriques et Monitoring Center
```

Les tests d'isolation et d'autorisation sont introduits avec chaque sous-lot concerné ; ils ne sont pas repoussés à la fin.

## 5. P1-B à P1-D — après validation du socle

- **P1-B :** dashboard authentifié, inventaire tenanté, connecteur de simulation intégré et données explicitement marquées `simulated: true`.
- **P1-C :** connecteurs Proxmox et Debian en lecture seule, comptes dédiés à privilèges minimaux, allowlist réseau et secrets via références vers un gestionnaire dédié.
- **P1-D :** collecte de métriques, VictoriaMetrics, seuils et historique ; pas de rétention longue des métriques dans PostgreSQL.

## 6. Définition de terminé pour chaque sous-lot

- PR séparée et empilée sur la branche de Phase 1 précédente ;
- critères d'acceptation écrits avant le code ;
- migrations et tests automatisés inclus ;
- tests unitaires, intégration et négatifs exécutés ;
- lint, typecheck, build et CI verts ;
- aucun secret réel, aucune connexion à une infrastructure réelle ;
- documentation `PROJECT_STATUS.md`, `BACKLOG.md` et ce plan mise à jour ;
- compte rendu PR avec commit, fichiers, commandes, résultats et limites ;
- aucune fusion ou mise en production sans accord explicite.

## 7. Prochain lot

**P1-A0 — Fondation Alembic** est implémenté dans la PR #4, branche `phase1/p1-a0-alembic-foundation`, empilée sur la PR #3. GitHub indique que la PR est ouverte et non-draft. Run CI #64 : 5 tests API passed (1 avertissement pytest-asyncio), build des 4 images, Web, gitleaks, validation Compose et smoke réussis. Le smoke PostgreSQL confirme `alembic upgrade head`, présence de `citext`, `alembic downgrade base`, puis nouvel upgrade vers `0001_pg_extensions (head)`. La migration ne crée aucune table métier. **Limite importante :** le downgrade retire la révision Alembic mais conserve volontairement l'extension partagée `citext` ; ce n'est donc pas un retour complet à une base strictement vierge. La PR reste ouverte et non fusionnée.

**Prochain sous-lot : P1-A1 — organisations, utilisateurs et memberships**, sur une PR empilée après revue de P1-A0. Les tables et contraintes seront ajoutées sans exposer de routes métier avant l'authentification.
