# CHANGELOG.md — Enterprise Infrastructure Intelligence

Tous les changements notables du projet sont documentés ici.
Format inspiré de [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added — P1-A3.1 HTTP organization reads

- Session-authenticated GET endpoints for organizations, active members and organization roles.
- Server-side organization membership and permission checks; non-member tenants return 404 and missing permissions return 403.
- Session cookie path widened to `/api/v1` so the browser sends it to protected API resources; HttpOnly/Secure/SameSite and Origin/CSRF protections remain.
- HTTP integration tests cover unauthenticated, owner, viewer, inactive members, logout revocation and cross-tenant cases.
- CI run #145: 7/7 jobs, 72 API tests, Web, four Docker images/non-root, Compose smoke and Gitleaks.
- pip-audit clean on this tree; npm audit remains 7 findings (1 moderate, 5 high, 1 critical), exit 1, report-only.
- No write endpoints, OIDC/MFA, RLS or audit trail are claimed in this lot.


### Added — P1-A3 RBAC core (2026-11-26, PR #17 en revue)

- Modèles roles, permissions et role_permissions ; les rôles sont propres à une organisation.
- Migration 0005_rbac_core qui convertit les rôles texte des memberships en références role_id avec contrainte composite tenant/role et protège le downgrade contre la perte de rôles personnalisés.
- Service serveur de provisioning des rôles par défaut et de résolution/exigence des permissions.
- Tests modèles et service positifs/négatifs. PR #17 reste core-only ; les premières routes GET qui consomment `require_permission` sont livrées séparément dans PR #18 (run #145 7/7).


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

- L'audit npm reste report-only avec 7 vulnérabilités : 1 critique Next.js, 5 élevées (dont PostCSS, glob et Zod), 1 modérée minimatch ; npm audit retourne 1. Ne pas exposer le frontend à un environnement non maîtrisé avant remédiation.
- Les arbres Python P1-A1/P1-A3 actuels passent pip-audit sans avis connus ; les branches plus anciennes peuvent encore conserver les 8 avis uniques de pytest/Starlette.
- PR #17 livre le core RBAC (modèles, migration 0005, service) ; PR #18 branche `require_permission` sur les premières lectures GET organisation/membres/rôles (run #145 7/7). Les mutations/gestion des rôles, RLS et audit trail restent non livrés.
- OIDC/MFA, isolation RLS complète, audit trail métier append-only et connecteurs Proxmox/Debian réels ne sont pas livrés.
- Le frontend de démonstration conserve des données simulées ; seul le healthcheck API est réellement connecté.
- La validation Compose sur le poste de développement n'a pas été effectuée dans ce cycle ; les preuves actuelles proviennent de GitHub Actions.
