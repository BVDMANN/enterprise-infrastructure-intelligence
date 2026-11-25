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
| Environnements Docker (compose + Dockerfiles) | IN_REVIEW — compose config OK ; COPY corrigés (PR audit) ; build non testé (pull Hub impossible ici) ; `compose up` non testable dans la VM (sandbox) |
| CI initiale (GitHub Actions) | TESTED — 33 runs ; 4 derniers verts, dernier run 4/4 jobs (gitleaks, API, Web, Compose) |
| Squelettes api / web / worker / connecteur-sim | TESTED — re-vérifiés pendant l'audit (pytest 3 passed, build web OK, API live OK, connecteur-sim OK, worker OK) |
| Vérification de l'environnement de dev | ACCEPTED — Docker installé 24/11 (29.1.3 + Compose v5.8.0) ; limites sandbox documentées (PROJECT_STATUS §5) |

### Audit suite — instruction ChatGPT du 25/11 (PR de suivi distincte, non fusionnée)

| Tâche | Statut |
|---|---|
| CI : build des 4 images Docker (`docker-build`) | IN_REVIEW — implémenté, CI de la PR de suivi à vérifier (jamais exécuté nulle part avant) |
| CI : smoke test `compose up` + healthchecks (`compose-smoke`) | IN_REVIEW — implémenté, CI de la PR de suivi à vérifier |
| CI : audit de dépendances report-only (`security-audit` : pip-audit + npm audit) | IN_REVIEW — implémenté, première exécution attendue en CI (`npm audit` non exécutable dans la VM d'audit) |
| Conteneurs non-root (USER app / USER node) + `--reload` retiré | IN_REVIEW — implémenté, vérification `id -u` en CI à confirmer |
| Healthchecks api / web / worker (+ `.dockerignore` `.env*.local`) | IN_REVIEW — implémenté, CI de la PR de suivi à vérifier |
| Split requirements API (runtime vs dev) | IN_REVIEW — implémenté, CI de la PR de suivi à vérifier |
| Audit sécurité concret (`docs/security/SECURITY_AUDIT_2026-11-25.md`) | TESTED — 8 vulnérabilités Python signalées (starlette, pytest) ; npm audit exécuté en CI (run #39) : 7 vulnérabilités (1 moderate, 5 high, 1 critical — next, postcss, zod, glob, minimatch) ; écarts description PR #2 documentés |
| Correction de la description de la PR #2 (affirmations inexactes) | TODO — à faire avant fusion de la PR #2 (voir audit sécurité §9) |
| Montée FastAPI (starlette ≥ 0.47.2 puis 1.x) — lot dédié avec re-tests | TODO — planifié, pas de patch silencieux |
| Montée Node 22 / Next 16 / React 19 / ESLint 10 — lot dédié | TODO — planifié (ESLint 8 en fin de vie) |

## PHASE 1 — MVP fonctionnel (à venir)

Critère de sortie : un utilisateur peut connecter un environnement de
test, synchroniser des ressources, les visualiser et consulter des
métriques fiables.

| # | Tâche | Statut | Dépendances |
|---|---|---|---|
| P1-01 | Valider `docker compose up --build` sur une machine Docker normale (Docker déjà installé sur la VM d'audit ; build/up non testables ici — sandbox sans bridge, pull Hub impossible ; la CI valide désormais build + smoke test, reste la confirmation du workflow dev local) | TODO | — (bloque P1-02+) |
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
| P1-13 | Migrations Alembic initiales (modèle §8, entités PHASE 1) | TODO | P1-01 |
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
