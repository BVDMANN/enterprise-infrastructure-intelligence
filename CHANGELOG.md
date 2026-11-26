# CHANGELOG.md — Enterprise Infrastructure Intelligence

Tous les changements notables du projet sont documentés ici.
Format inspiré de [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added — PHASE 0 (2026-11-24)

- Structure complète du repository (§6 de la spécification V3).
- Documentation de base : PRODUCT_REQUIREMENTS, SYSTEM_ARCHITECTURE,
  TECHNICAL_SPECIFICATION, DATABASE_DESIGN, API_SPECIFICATION,
  CONNECTOR_SPECIFICATION, SECURITY_ARCHITECTURE, THREAT_MODEL (STRIDE),
  AI_GOVERNANCE, ADR_INDEX + ADR-0001 à ADR-0005, BACKLOG, PROJECT_STATUS.
- Squelettes : API FastAPI (`/health`, `/api/v1/health`), web Next.js
  (App Router, TypeScript strict, Tailwind, shadcn/ui), worker Celery,
  connecteur de simulation (données marquées SIMULÉ).
- `docker-compose.yml` de développement (PostgreSQL 16, Redis 7, api,
  worker, web, connector-sim) + Dockerfiles.
- CI GitHub Actions initiale (lint/typecheck/build web, lint/tests
  backend, scan secrets gitleaks, validation compose).
- `scripts/check-env.sh` (vérification de l'environnement de dev).

### Known issues (snapshot initial du 24/11/2026 — statut actualisé ci-dessous)

- La validation Docker locale sur la VM de développement n'est pas confirmée ; la CI hébergée exécute les builds des images et le smoke Compose (runs #67, #73, #74, #76 et #77).
- P1-A0 (migration Alembic `0001_pg_extensions`) et P1-A1 (organisations, utilisateurs, memberships) sont implémentés dans des PR ouvertes ; OIDC/sessions, RBAC, contexte tenant/RLS, audit trail et endpoints métier restent non implémentés.


### Updated — 2026-11-25

- P1-A1 : PR #8 ajoute les contrôles `is_active` et `deleted_at` aux deux lectures tenant-scoped et deux tests négatifs ; run CI #76 : 7/7 jobs réussis, 32 tests API.
- Interface : PR #6 livre les pages de démonstration navigables ; les données métier restent explicitement fictives et seul le healthcheck appelle l'API.
- CI : PR #7 migre les actions GitHub et Gitleaks vers des versions Node 24 ; run #77 : 7/7 jobs réussis, aucun avertissement runtime Node 20 dans les logs.
- Audits : pip-audit signale encore 16 occurrences dans pytest 8.3.4 et Starlette 0.41.3 ; npm audit signale 7 vulnérabilités (1 modérée, 5 élevées, 1 critique). Les audits restent report-only.
- Les PR #2 à #8 sont ouvertes et non fusionnées ; aucune authentification OIDC/session ni route métier tenantée n'est revendiquée comme terminée.


### Updated — 2026-11-25 (23:58 CET)

- P1-A2.1 : PR #10 ajoute des sessions serveur opaques, hashées, expirables et révocables ; run #92 : 7/7 jobs CI réussis. PR ouverte/non fusionnée.
- P1-A2.2 : PR #11 ajoute l'authentification locale Argon2id et les routes login/me/logout avec cookie HttpOnly et CSRF. Run #104 : 7/7 jobs réussis sur la tête `acb12af`, API 55 tests passés et 1 avertissement ; l'audit report-only signale encore 16 occurrences Python et 7 vulnérabilités npm.
- OIDC provider et challenge MFA non implémentés ; RBAC, contexte tenant/RLS et audit trail restent à construire.
- PR #12 met à niveau FastAPI, pytest et pytest-asyncio ; run #98 : 7/7 jobs réussis et pip-audit sans vulnérabilité Python sur cette branche. Le commit `8b1e157` ajoute `httpx2==2.16.2` pour le TestClient Starlette ; run #107 terminé 7/7, pip-audit propre et aucun avertissement Starlette/TestClient dans les logs API. L'audit npm signale toujours 7 vulnérabilités et reste report-only.
- La PR #11 ajoute aussi `argon2-cffi` dans `apps/api/requirements.txt` : les mises à niveau des PR #11 et #12 doivent être combinées et revalidées avant acceptation.
- Aucune PR n'a été fusionnée et aucun déploiement n'a été effectué.


### Updated — 2026-11-26 (01:34 CET)

- PR #13 synchronise les dépendances Python avec l'authentification locale de PR #11 sans toucher au code métier : FastAPI 0.162.0, Argon2id 25.1.0 conservé, pytest 9.0.3, pytest-asyncio 1.4.1, httpx2 2.16.2 et configuration explicite des fixtures asyncio.
- Run CI #114 (ID `45727322292`) sur `a92ae9f` : 7/7 jobs réussis ; API 55 tests, Web lint/typecheck/build, Docker build, Compose config/smoke, Gitleaks. API/Web/Worker healthy et connecteur de simulation exit 0 ; ports hôte liés à 127.0.0.1.
- pip-audit ne trouve aucun avis connu sur l'arbre Python combiné. npm audit reste en échec (exit code 1) avec 7 vulnérabilités (1 modérée, 5 élevées, 1 critique) ; audit global report-only, aucune correction npm revendiquée.
- PR #7 valide séparément les actions Node 24 (run #77, 7/7), mais PR #13 n'en descend pas et conserve les avertissements Node 20 des actions checkout/setup-node/setup-python.
- OIDC/MFA, RBAC, isolation tenant/RLS et audit trail métier restent non implémentés. Aucune PR fusionnée ni aucun déploiement.


### Updated — 2026-11-26 (03:24 CET)

- P1-A0 / PR #4 : run CI #117 (ID `45730025314`) terminé 7/7 sur la tête `25091e0`, incluant migration PostgreSQL dans le smoke Compose.
- Documentation / PR #9 : run CI #116 (ID `45729950390`) terminé 7/7 sur la tête `d12bb55`.
- P1-A1 / PR #5 : run #73 7/7 ; la tête de base P1-A0 a reçu un commit documentaire supplémentaire, laissant #5 à 1 commit derrière sans chevauchement de fichiers. PR #5 n'a pas été modifiée.
- P1-A2 / PR #13 : run #114 7/7 ; 55 tests API, lint/typecheck/build Web, Docker, Compose config/smoke et Gitleaks réussis. pip-audit ne trouve aucun avis connu sur l'arbre Python combiné.
- npm audit reste en échec (exit code 1) avec 7 vulnérabilités : 1 modérée, 5 élevées et 1 critique. Le job reste report-only ; aucune correction npm n'est revendiquée.
- Les logs #114 signalent Node 20 forcé vers Node 24 pour checkout@v4, setup-node@v4 et setup-python@v5 ; les logs #116/#117 signalent checkout@v4 et gitleaks-action@v2. La PR #7 porte la migration Node 24, mais elle n'est pas intégrée à ces branches.
- OIDC/MFA, RBAC, isolation tenant/RLS et audit trail métier restent non livrés. Les données métier de la PR #6 restent simulées.
