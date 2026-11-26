# PHASE1_PLAN.md — Enterprise Infrastructure Intelligence

> Version : 1.1 — 26 novembre 2026
> Branche de préparation : `audit/phase-0-followup`
> Statut : plan de livraison ; premières lectures HTTP organisation/membres/rôles en cours de validation ; aucun accès infrastructure réelle ajouté.

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
| G0 — CI/Compose | Build des 4 images, configuration Compose et smoke test complets | TESTED — run #134, 7/7 jobs |
| G1 — Ports locaux | DB/Redis/API/Web publiés uniquement sur 127.0.0.1 ; assertion CI | TESTED — run #134, assertions Compose et smoke |
| G2 — Runtime Web | Node applicatif 22 sur Docker ; actions GitHub Node 24 ; lint, typecheck, build et smoke | TESTED — runs #120/#127/#134 |
| G3 — Audit dépendances | Résultats actuels documentés, job explicitement report-only | TESTED / REPORT-ONLY — pip-audit propre sur P1-A1/P1-A3 ; npm audit 7 vulnérabilités (1 modérée, 5 élevées, 1 critique), exit 1 |
| G4 — Poste développeur | `docker compose up --build` validé sur le poste local | À confirmer localement |

G0–G3 sont validées par les runs CI #120, #127, #134 et #135. G4 reste une vérification locale non revendiquée par ce cycle. Les audits restent report-only : les arbres Python P1-A1/P1-A3 actuels sont propres, mais les arbres anciens gardent des avis ; npm reste à 7 vulnérabilités et doit être traité dans une migration web isolée. Les avertissements Gitleaks v3 DEP0040/DEP0169 restent visibles.

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

**État : modèles SQLAlchemy 2, migration `0002_identity` et lectures limitées au membership livrés dans la PR #5 ouverte (non fusionnée).** La PR #5 n'inclut pas de route publique ; les premières lectures HTTP sont ajoutées séparément dans le lot P1-A3.1 (PR #18, en validation CI), sans invitation ni mutation. La PR #17 ajoute la migration 0005 qui remplace le rôle texte par un `role_id` tenant-scoped et valide le backfill PostgreSQL.

### P1-A2 — Sessions et OIDC

**But :** authentifier les utilisateurs sans implémenter un fournisseur propriétaire.

Travail :
- interface OIDC provider indépendante du fournisseur ;
- validation stricte issuer, audience, signature, nonce, state et expiration ;
- sessions serveur avec token opaque, hashé en base, expiration et révocation ;
- cookies Secure, HttpOnly, SameSite adaptés ; CSRF et vérification Origin pour les mutations ;
- aucune conservation de bearer token brut en base ou dans les logs.

État : sessions serveur et authentification locale sont présentes dans les PR #10/#11/#13/#14. L'adaptateur OIDC, la validation JWKS et le MFA effectif ne sont pas encore livrés ; aucun login fédéré n'est revendiqué.

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
- rôles strictement propres à une organisation (organization_id NOT NULL) ; rôles plateforme globaux différés ;
- permissions nommées et table de liaison role_permissions ;
- rôle effectif résolu à partir du membership actif.

Tests négatifs :
- membre lecteur ne peut pas modifier ;
- membre sans permission ne peut pas appeler l'action ;
- rôle d'une organisation A non réutilisable dans B ;
- tentative d'élévation de rôle refusée côté service ; journalisation métier à intégrer avec P1-A5.

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

**P1-A1 — Organisations, utilisateurs et memberships** est livré sur la branche `phase1/p1-a1-organisations-utilisateurs` (PR #5, ouverte, non fusionnée). Modèles SQLAlchemy 2, migration `0002_identity`, lectures limitées au membership ; aucune route métier d'organisation ou d'invitation n'est ouverte. Le rôle texte historique est remplacé par `role_id` tenant-scoped dans la migration 0005 proposée en PR #17. Détails : PROJECT_STATUS.md §14.

**P1-A2 :** sessions serveur et authentification locale sont présentes dans les PR #10/#11/#13/#14 ; OIDC/JWKS et MFA restent à livrer dans un module isolé. **P1-A3 core :** PR #17, modèle/migration/service validés par runs #134/#135 ; les guards HTTP et endpoints de gestion des rôles restent à intégrer.


### État de livraison P1-A3 — PR #17 (brouillon, CI 7/7 run #135, revue indépendante en attente)

Le lot RBAC core est implémenté sur une branche empilée sur la tête P1-A2 validée (#14), sans modifier les branches #10 à #14 :

- Tables roles, permissions et role_permissions, avec unicité des noms et liaison composite de memberships(organization_id, role_id) vers roles(organization_id, id).
- Migration 0005_rbac_core : conversion des anciens rôles texte en rôles système propres à chaque organisation, attribution d'un catalogue de permissions et downgrade protégé contre la perte de rôles ou d'affectations personnalisés.
- Service serveur pour provisionner les rôles par défaut et résoudre/exiger les permissions depuis l'utilisateur actif, le membership et l'organisation actifs.
- Tests modèles/service positifs et négatifs : rôles et permissions uniques, utilisateur sans membership, compte inactif/supprimé, organisation supprimée, refus d'une permission et impossibilité d'affecter un rôle d'un autre tenant.

**Limite explicite :** cette PR livre le modèle, la migration et le service d'autorisation ; aucun endpoint métier ni dépendance FastAPI RBAC n'est encore branché. Les routes devront appeler require_permission dans un lot d'intégration distinct avant que RBAC soit considéré comme appliqué à l'API. Les rôles plateforme globaux sont différés ; les rôles de ce lot sont strictement organisationnels.

Les runs #134 (code/backfill) et #135 (tête documentaire) sont verts 7/7 ; le dernier teste la tête 0a724b6 : 67 tests API, Ruff check/format, Web, 4 images Docker, non-root, Compose config/smoke et Gitleaks. Le smoke PostgreSQL vérifie le backfill d'un ancien membership owner, ses 9 permissions, le rejet d'une affectation inter-tenant par la FK composite, le downgrade qui restaure le rôle texte puis un nouvel upgrade head. PR #17 reste en brouillon et en revue indépendante ; aucun endpoint RBAC métier n'est encore branché.

### P1-A3.1 — enforcement HTTP initial (branche `phase1/p1-a3-rbac-http-api`)

Le lot enfant ajoute une dépendance de session active et les premières routes GET
organisation/membres/rôles. Chaque route vérifie le membership de l'utilisateur et la
permission correspondante côté serveur ; un tenant étranger retourne 404 et un membre
sans permission retourne 403. La liste des organisations filtre également sur
`organization.read`.

Le cookie de session est étendu à `Path=/api/v1` (et supprimé avec le même chemin),
car `Path=/api/v1/auth` empêchait le navigateur de transmettre la session aux routes
métier. Les attributs HttpOnly, Secure hors développement, SameSite=Lax, le contrôle
Origin et le CSRF logout sont conservés.

Acceptation attendue : tests HTTP login→organisations, 401 sans session, 404 inter-tenant,
403 par permission, lecture owner, refus viewer, liste membres sans comptes inactifs,
Ruff, tests API, quatre images Docker, non-root, Compose config/smoke et Gitleaks.
Aucune mutation, invitation, gestion de rôle, OIDC/MFA, RLS ou audit trail n'est incluse.
