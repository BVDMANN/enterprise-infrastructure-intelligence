# BACKLOG.md — Enterprise Infrastructure Intelligence

> Priorisation PHASE 1 (MVP) — spécification V3 §21.
> Statuts : `TODO` · `IN_PROGRESS` · `BLOCKED` · `IN_REVIEW` ·
> `TESTED` · `ACCEPTED` · `DEPLOYED`.
> Rappel : développé ≠ testé ≠ accepté ≠ déployé ≠ prêt pour la production.

## PHASE 0 — Fondations (terminée, en attente de validation)

| Tâche | Statut |
|---|---|
| Audit du repository existant (greenfield confirmé) | ACCEPTED |
| Structure du repository (§6) | ACCEPTED |
| Documentation de base (15 fichiers : 9 docs + ADR_INDEX + 5 ADR) | ACCEPTED |
| Environnements Docker (compose + Dockerfiles) | TESTED — run #54 : build des 4 images, config Compose, healthchecks et smoke complets réussis ; confirmation du poste local encore à consigner |
| CI initiale (GitHub Actions) | TESTED — 33 runs ; 4 derniers verts, dernier run 4/4 jobs (gitleaks, API, Web, Compose) |
| Squelettes api / web / worker / connecteur-sim | TESTED — re-vérifiés pendant l'audit (pytest 3 passed, build web OK, API live OK, connecteur-sim OK, worker OK) |
| Vérification de l'environnement de dev | ACCEPTED — Docker installé 24/11 (29.1.3 + Compose v5.8.0) ; limites sandbox documentées (PROJECT_STATUS §5) |

### Audit suite — instruction ChatGPT du 25/11 (PR de suivi distincte, non fusionnée)

| Tâche | Statut |
|---|---|
| CI : build des 4 images Docker (`docker-build`) | TESTED — run #54, 4 images construites ; contrôle non-root réussi (uid 999/1000) |
| CI : smoke test `compose up` + healthchecks (`compose-smoke`) | TESTED — run #54 : API/Web/Worker healthy, endpoints vérifiés, connecteur-sim exit 0, ports hôte sur 127.0.0.1 |
| CI : audit de dépendances report-only (`security-audit` : pip-audit + npm audit) | TESTED / REPORT-ONLY — run #54 : pip-audit 16 occurrences / 8 avis uniques ; npm audit 7 vulnérabilités (1 moderate, 5 high, 1 critical). Job vert grâce à `continue-on-error`, pas « zéro vulnérabilité » |
| Conteneurs non-root (USER app / USER node) + `--reload` retiré | TESTED — run #54 : API/Worker/Connector uid 999, Web uid 1000 |
| Healthchecks api / web / worker (+ `.dockerignore` `.env*.local`) | TESTED — run #54 : healthchecks API/Web/Worker verts ; règles `.env*.local` conservées |
| Split requirements API (runtime vs dev) | TESTED — run #54 : installation requirements-dev, ruff et pytest réussis |
| Audit sécurité concret (`docs/security/SECURITY_AUDIT_2026-11-25.md`) | TESTED — revalidé run #54 : pip-audit 16 occurrences / 8 avis uniques (Starlette 0.41.3, pytest 8.3.4) ; npm audit 7 vulnérabilités (1 moderate, 5 high, 1 critical) ; report-only documenté |
| Correction de la description de la PR #2 (affirmations inexactes) | DONE — corps de PR #2 corrigé le 25/11, affirmations fausses retirées |
| Montée FastAPI (starlette ≥ 0.47.2 puis 1.x) — lot dédié avec re-tests | TODO — planifié, pas de patch silencieux |
| Runtime Node 22 (Docker + CI) | TESTED — run #54 : npm ci/lint/typecheck/build + image Docker Web + Compose smoke réussis sur Node 22 |

## PHASE 1 — MVP fonctionnel (à venir)

Critère de sortie : un utilisateur peut connecter un environnement de
test, synchroniser des ressources, les visualiser et consulter des
métriques fiables.

| # | Tâche | Statut | Dépendances |
|---|---|---|---|
| P1-01 | Valider le workflow `docker compose up --build` sur le poste de développement ; CI run #54 : 4 images + Compose smoke validés, reste la confirmation locale | TODO | — (bloque P1-02+) |
| P1-02 | Authentification OIDC + sessions + MFA | TODO | P1-01 |
| P1-03 | Organisations, membres, invitations | TODO | P1-02 |
| P1-04 | Rôles et permissions (RBAC) + tests d'autorisation | TODO | P1-02 |
| P1-05 | Dashboard central (états chargement/vide/erreur, données du backend) | TODO | P1-04 |
| P1-06 | Infrastructure Manager (inventaire, recherche, filtres, détails) | TODO | P1-04 |
| P1-07 | Connecteur de simulation (intégré au dashboard) | TODO | P1-06 |
| P1-08 | Connecteur Proxmox lecture seule (nœuds, VM, conteneurs, métriques) | TODO | P1-06 |
| P1-09 | Connecteur Debian lecture seule (OS, CPU, RAM, stockage, services) | TODO | P1-06 |
| P1-10 | Première collecte de métriques (VictoriaMetrics) | TODO | P1-08/P1-09 |
| P1-11 | Monitoring Center (graphiques, seuils, historique) | TODO | P1-10 |
| P1-12 | Audit de base (journal des opérations sensibles) | TODO | P1-02 |
| P1-A0 | Fondation Alembic + migration `citext` + cycle upgrade/downgrade PostgreSQL 16 | TESTED — PR #4 ouverte (non-draft), run #64 : 5 tests API passed ; migration/extension/transition downgrade puis nouvel upgrade validés en Compose ; l'extension citext est volontairement conservée au downgrade | P1-01 |
| P1-13 | Migrations Alembic des entités métier (organisations, utilisateurs, memberships, RBAC) | TODO — prochain sous-lot P1-A1 après revue de P1-A0 | P1-A0 |
| P1-14 | Tests d'isolation multi-tenant (+ évaluation RLS, ADR-0005) | TODO | P1-04, P1-13 |
| P1-15 | Tests backend / frontend / e2e (Playwright) du MVP | TODO | P1-05…P1-12 |
| P1-16 | Documentation mise à jour (API, déploiement, opérations) | TODO | P1-15 |

## PHASE 2 — Supervision avancée et opérations

| Tâche | Statut |
|---|---|
| Alerting Center (règles, seuils, déduplication, acquittement) | TODO |
| Incident Management (cycle de vie complet, traçabilité) | TODO |
| Notifications (canaux, escalade) | TODO |
| Automation Engine (workflows, simulation, approbations) | TODO |
| Premières actions contrôlées + vérification post-exécution | TODO |

## PHASE 3 — Cloud et intelligence

| Tâche | Statut |
|---|---|
| AWS Manager (lecture seule, rôles IAM) | TODO |
| Cost Intelligence | TODO |
| AI Operations Assistant (via moteur de politiques) | TODO |
| Analyse d'incidents, recommandations, rapports, tendances | TODO |

## PHASE 4 — Fonctionnalités Enterprise

| Tâche | Statut |
|---|---|
| SSO / MFA avancée | TODO |
| Administration SaaS avancée, quotas | TODO |
| Facturation (Billing & Subscription) | TODO |
| Rapports d'audit avancés, rétention | TODO |
| Renforcement de la résilience, préparation déploiement dédié | TODO |

## PHASE 5 — Préparation commerciale

| Tâche | Statut |
|---|---|
| Site commercial (15 pages, sans clients/références inventés) | TODO |
| Documentation utilisateur / administrateur / déploiement | TODO |
| Démonstration, onboarding, support | TODO |
| Dossier de sécurité, dossier technique, maintenance | TODO |


## Suivi de revue du 25/11/2026 — run CI #54

- Ports Compose 5432/6379/8000/3000 liés à `127.0.0.1`, avec assertion automatisée sur `docker compose config --format json` — TESTED.
- Node 22 (Dockerfile Web + CI) — TESTED : install, lint, typecheck, build, build image et Compose smoke verts.
- Les vulnérabilités Starlette/Pytest et npm restent ouvertes et suivies en report-only ; aucune mise à niveau majeure automatique n'a été appliquée.
- Runtime des actions GitHub encore averti (checkout@v4/setup-node@v4/setup-python@v5 Node 20 forcé vers Node 24) — lot CI séparé.
- Phase 1 : voir `PHASE1_PLAN.md`. L'implémentation métier ne démarre pas avant les critères de sécurité et la validation locale P1-01.
