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

**État : implémenté (25/11/2026, branche `phase1/p1-a1-organisations-utilisateurs`, PR #5 ouverte et non fusionnée, empilée sur PR #4 ; correctif de sécurité complémentaire PR #8 ouvert et non fusionné).** Aucune route publique ouverte, conformément au but du lot. Écarts documentés par rapport à `docs/architecture/DATABASE_DESIGN.md` : pas de `plan_id` sur `organizations` (la table `plans` n'existe pas encore — la FK viendra avec la facturation) ; `memberships.role` est une chaîne avec CHECK (owner/admin/member/viewer) en attendant la table `roles` de P1-A3 ; `oidc_subject` nullable (rempli à la première connexion OIDC, P1-A2) ; IDs générés côté Python (`uuid.uuid4`, équivalent de `gen_random_uuid()`).

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

## 7. État courant et prochain lot — P1-A2 Sessions et authentification

P1-A0 est en revue dans la PR #4 (run #67 : 7/7 jobs réussis). P1-A1 est en revue dans la PR #5 (run #73 : 7/7) et le correctif de lecture tenant-scoped PR #8 (run #76 : 7/7, 32 tests API). Ces PR restent ouvertes et non fusionnées.

### P1-A2.1 — Sessions serveur

**État :** implémenté dans la PR #10, branche `phase1/p1-a2-server-sessions`, tête `fff99f4`, ouverte/non fusionnée. Run #92 : 7/7 jobs CI réussis.

- Jetons de session opaques ; seuls les hash des jetons session et CSRF sont persistés.
- Expiration, révocation, refus des sessions expirées/révoquées et contrôle de l'état actif/supprimé de l'utilisateur.
- Tests positifs et négatifs du cycle de vie, du TTL et du CSRF.
- Pas encore de fournisseur OIDC ni de route login/logout dans ce sous-lot.

### P1-A2.2 — Authentification locale

**État :** en revue dans la PR #11, branche `phase1/p1-a2-local-auth`, draft, tête `acb12af`.

- Hash des mots de passe Argon2id ; refus des comptes inactifs, supprimés, OIDC-only ou MFA-enabled pour éviter un contournement du second facteur.
- Routes `POST /login`, `GET /me`, `POST /logout` avec cookie HttpOnly, SameSite, Origin, CSRF lié à la session et rate limiting Redis fail-closed.
- Tests de hash, politique de mot de passe, comptes invalides, login/me/logout, Origin et CSRF.
- Run #104 : **7/7 jobs réussis** sur la tête `acb12af` ; API **55 tests passés**, 1 avertissement. L'audit est report-only et signale encore 16 occurrences Python + 7 vulnérabilités npm.
- Le statut `mfa_enabled` bloque actuellement le login local ; aucun challenge OTP/MFA n'est encore disponible.

### P1-A2.3 — OIDC et MFA

**État : TODO.** Il reste à intégrer un fournisseur OIDC indépendant du fournisseur, avec validation stricte issuer, audience, signature, nonce, state et expiration, puis le flux MFA/challenge. Ne pas présenter l'authentification locale comme une intégration OIDC.

### Dépendances de sécurité associées

La PR #12 (`phase0/python-security-remediation`) met à niveau FastAPI/pytest/pytest-asyncio. Run #98 : 7/7 jobs réussis ; `pip-audit` ne trouve aucune vulnérabilité Python sur cette branche. Le commit `8b1e157` ajoute `httpx2==2.16.2` pour le TestClient Starlette ; run #107 terminé 7/7, pip-audit propre et aucun avertissement Starlette/TestClient dans les logs API. `npm audit` signale toujours 7 vulnérabilités (1 modérée, 5 élevées, 1 critique) et reste report-only. La PR #11 ajoute également `argon2-cffi==25.1.0` dans `apps/api/requirements.txt` : les deux modifications doivent être conservées lors de la synchronisation, puis testées ensemble par pip install, Ruff, pytest, build Docker et Compose smoke. L'audit du run #104 sur la branche #11 signale encore 16 occurrences Python et 7 npm, car la mise à niveau #12 n'y est pas intégrée.

### Prochain lot concret

1. Terminer et relire le run #104 de la PR #11 ; accepter uniquement si API, Web, Gitleaks, audit, Docker build, Compose config et smoke sont tous terminés sans échec.
2. Synchroniser les dépendances PR #11/#12 sans écraser FastAPI ni `argon2-cffi`, puis relancer l'audit combiné. Les vulnérabilités npm restent à traiter séparément.
3. Compléter OIDC/MFA et leurs tests négatifs avant de déclarer P1-A2 terminé.
4. Ouvrir ensuite P1-A3 RBAC avec modèle de permissions, enforcement côté API et tests positifs/négatifs ; poursuivre avec contexte tenant/RLS (P1-A4), puis audit trail (P1-A5).

La PR #6 fournit une interface de démonstration navigable, mais ses données métier restent simulées ; seul le healthcheck appelle l'API réelle. Les endpoints métier et l'authentification ne sont pas encore intégrés à l'interface. La PR #7 traite séparément les actions GitHub Node 24 (run #77 : 7/7 jobs réussis).

Aucune fusion, aucun déploiement et aucun secret réel sans accord explicite.
