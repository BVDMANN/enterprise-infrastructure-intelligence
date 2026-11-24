# TECHNICAL_SPECIFICATION.md — Enterprise Infrastructure Intelligence

> Version : spécification V3. Statut : PHASE 0.

## 1. Stack obligatoire (ADR-0002)

| Couche | Choix | Version de référence |
|---|---|---|
| Frontend | Next.js App Router, React, TypeScript strict | Next.js 14, React 18, TS 5 |
| UI | Tailwind CSS, shadcn/ui, Lucide Icons | Tailwind 3 |
| Data (front) | TanStack Query, React Hook Form, Zod, Recharts | — |
| Backend | Python, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic | Python 3.12 |
| Base métier | PostgreSQL | 16 |
| Cache / file | Redis + Celery | Redis 7 |
| Métriques | VictoriaMetrics (+ Prometheus si pertinent) | — |
| Conteneurs | Docker, Docker Compose | — |
| CI/CD | GitHub Actions | — |
| Télémétrie | OpenTelemetry | — |
| Tests | pytest (backend), Playwright (e2e) | — |
| Auth | OIDC (+ MFA, préparation SAML/SSO) | — |
| Secrets | Interface compatible HashiCorp Vault (ou équivalent) | — |

Toute modification de stack exige un ADR (décrire le problème, les
conséquences, la solution justifiée — ne jamais modifier silencieusement).

## 2. Repository

Structure §6 de la spécification (voir `README.md`). Branches :
`main` (stable, protégée), `develop` (intégration), `feature/*`,
`fix/*`, `security/*`. Aucune fonctionnalité importante fusionnée sans
revue. Chaque PR : objectif, description, fichiers, risques, tests,
captures si nécessaire, impacts base de données, documentation modifiée.

## 3. Conventions de code

- **Python** : typage explicite, `ruff` (lint + format), docstrings pour
  les fonctions publiques, pas d'import circulaire entre modules métier.
- **TypeScript** : `strict: true`, pas de `any` implicite, Zod pour toute
  validation d'entrée, `eslint` + `prettier`.
- **Nommage** : anglais pour le code et les commentaires ; français pour
  la documentation produit et les messages utilisateur de la spec.
- **Erreurs** : jamais de stack trace ni de secret exposé au client ;
  codes d'erreur stables et documentés (voir `API_SPECIFICATION.md`).
- **Dates** : UTC en base, fuseau horaire explicite à l'affichage (ISO 8601).

## 4. Base de données

PostgreSQL 16 pour le métier (voir `DATABASE_DESIGN.md`) ; Redis pour
cache, tâches et mécanismes temporaires ; Celery pour l'asynchrone ;
**ne pas stocker indéfiniment les métriques dans PostgreSQL** —
VictoriaMetrics pour le moyen/long terme. Migrations Alembic obligatoires,
revues comme du code.

## 5. API

REST versionnée sous `/api/v1`, OpenAPI généré par FastAPI, documentation
exploitable (voir `API_SPECIFICATION.md`). Opérations longues =
asynchrones avec identifiant de tâche consultable. Limitation de débit,
idempotence quand nécessaire, pagination/filtres/tri/recherche.

## 6. Sécurité (renvoi)

Voir `docs/security/SECURITY_ARCHITECTURE.md` et `THREAT_MODEL.md`.
Points structurants : HTTPS obligatoire, mTLS connecteurs, MFA, RBAC
côté serveur, validation stricte des entrées, secrets jamais en clair,
journalisation des opérations sensibles (sans mot de passe/token en clair).

## 7. Tests et qualité

- Backend : unitaires, intégration, API, autorisation, multi-tenancy,
  validation, migrations, connecteurs, erreurs, concurrence si pertinent.
- Frontend : composants, formulaires, navigation, états de chargement,
  erreurs, permissions, responsive.
- E2E : Playwright, parcours complets (voir `ACCEPTANCE_TESTS.md`).
- Sécurité : contrôle des permissions, isolation des organisations,
  sessions, injections, dépendances, images Docker.
- Performance : objectifs mesurables avant toute déclaration de charge.
- CI obligatoire : lint, typecheck, tests, build, formatage, scan
  secrets, scan dépendances, analyse statique, scan images.

## 8. Environnements et déploiement

Docker Compose en dev ; GitHub Actions en CI/CD ; déploiement compatible
Kubernetes à terme. Health/readiness/liveness checks partout. Sauvegardes
chiffrées, restauration testée (pas seulement sauvegardée).
