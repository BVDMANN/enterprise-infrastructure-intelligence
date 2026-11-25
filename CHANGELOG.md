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

### Known issues

- Docker absent de la VM de développement : `docker compose up`
  non testé (voir PROJECT_STATUS.md §5).
- Aucun module métier implémenté ; aucune migration Alembic créée ;
  OIDC/RBAC non implémentés (squelettes uniquement).


### Updated — 2026-11-25

- P1-A1 : PR #8 ajoute les contrôles `is_active` et `deleted_at` aux deux lectures tenant-scoped et deux tests négatifs ; run CI #76 : 7/7 jobs réussis, 32 tests API.
- Interface : PR #6 livre les pages de démonstration navigables ; les données métier restent explicitement fictives et seul le healthcheck appelle l'API.
- CI : PR #7 migre les actions GitHub et Gitleaks vers des versions Node 24 ; run #77 : 7/7 jobs réussis, aucun avertissement runtime Node 20 dans les logs.
- Audits : pip-audit signale encore 16 occurrences dans pytest 8.3.4 et Starlette 0.41.3 ; npm audit signale 7 vulnérabilités (1 modérée, 5 élevées, 1 critique). Les audits restent report-only.
- Les PR #2 à #8 sont ouvertes et non fusionnées ; aucune authentification OIDC/session ni route métier tenantée n'est revendiquée comme terminée.
