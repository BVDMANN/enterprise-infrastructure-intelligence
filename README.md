# Enterprise Infrastructure Intelligence

Plateforme SaaS B2B de gestion intelligente des infrastructures informatiques —
visibilité, contrôle, intelligence opérationnelle et optimisation — pour ETI,
grandes entreprises et, à terme, administrations.

> **Statut : PHASE 0 — fondations.** Aucun module métier n'est encore implémenté.
> Voir [PROJECT_STATUS.md](PROJECT_STATUS.md) pour l'état exact.
> Nom de travail provisoire : *Enterprise Infrastructure Intelligence*.

## Vision (résumé)

Centraliser la supervision, l'administration et l'optimisation d'un système
d'information hybride (serveurs physiques, VM, Proxmox, Linux, cloud AWS)
depuis une interface unique, sans remplacer les outils existants.

Quatre capacités : **Visibility · Control · Intelligence · Optimization**.

## Stack (fixée par la spécification V3 — voir `docs/decisions/`)

| Couche | Technologie |
|---|---|
| Frontend | Next.js App Router, React, TypeScript strict, Tailwind CSS, shadcn/ui, TanStack Query, React Hook Form, Zod, Recharts, Lucide |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Données | PostgreSQL 16, Redis 7, Celery, VictoriaMetrics / Prometheus (métriques) |
| Infra | Docker, Docker Compose, GitHub Actions, OpenTelemetry, pytest, Playwright |
| Auth | OIDC (+ MFA, préparation SAML/SSO), RBAC |

## Architecture (résumé)

Monolithe modulaire : **Control Plane** (SaaS central : web, API, workers) et
**Data Plane** (connecteurs/agents chez le client, connexions sortantes
chiffrées, mTLS, identité unique par connecteur). Détail :
[docs/architecture/SYSTEM_ARCHITECTURE.md](docs/architecture/SYSTEM_ARCHITECTURE.md).

## Démarrage (développement)

Prérequis : Docker + Docker Compose, Node.js 20+, Python 3.12+.

```bash
cp .env.example .env        # puis renseigner les valeurs (jamais de secret réel en clair)
docker compose up --build
# Web : http://localhost:3000 — API : http://localhost:8000 — API docs : http://localhost:8000/docs
```

Sans Docker (vérification locale uniquement) : voir `scripts/check-env.sh`.

## Structure

```
apps/web        # Next.js App Router (TypeScript strict)
apps/api        # FastAPI (Python 3.12, SQLAlchemy 2, Alembic)
services/worker # Celery — traitements asynchrones
services/connector # Connecteurs Data Plane (simulation + Proxmox/Debian à venir)
packages/shared-types # Types TypeScript partagés
packages/ui     # Design system (shadcn/ui)
infrastructure/ # Docker, déploiement, monitoring
docs/           # Spécifications, architecture, sécurité, décisions (ADR)
tests/          # unit, integration, e2e, security, performance
```

## Règles absolues

1. Aucune donnée fictive présentée comme réelle — les données de
   démonstration sont explicitement marquées **SIMULÉ**.
2. Aucun secret en clair dans le code ou dans Git.
3. Aucune action sensible sans autorisation ; les permissions sont
   contrôlées côté serveur, jamais uniquement dans le frontend.
4. Multi-tenancy dès le départ : toute requête est limitée à
   l'organisation autorisée.
5. Aucun déploiement en production sans validation humaine.

## Documentation

- Spécifications : [docs/](docs/) — produit, architecture, API, base de
  données, connecteurs, sécurité, gouvernance IA.
- Décisions d'architecture : [docs/decisions/ADR_INDEX.md](docs/decisions/ADR_INDEX.md)
- État du projet et backlog PHASE 1 : [PROJECT_STATUS.md](PROJECT_STATUS.md)
  et [BACKLOG.md](BACKLOG.md)
- Contribution : [CONTRIBUTING.md](CONTRIBUTING.md) — Sécurité :
  [SECURITY.md](SECURITY.md)
