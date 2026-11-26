# CHANGELOG.md — Enterprise Infrastructure Intelligence

Tous les changements notables du projet sont documentés ici.
Format inspiré de [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added — P1-A3 RBAC core (2026-11-26, PR #17 en revue)

- Modèles roles, permissions et role_permissions ; les rôles sont propres à une organisation.
- Migration 0005_rbac_core qui convertit les rôles texte des memberships en références role_id avec contrainte composite tenant/role et protège le downgrade contre la perte de rôles personnalisés.
- Service serveur de provisioning des rôles par défaut et de résolution/exigence des permissions.
- Tests modèles et service positifs/négatifs ; aucun endpoint RBAC métier n'est encore branché.


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
