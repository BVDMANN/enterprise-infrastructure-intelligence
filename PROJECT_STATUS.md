# PROJECT_STATUS.md — Enterprise Infrastructure Intelligence

> Dernière mise à jour : **24 novembre 2026** (fin de PHASE 0).
> Spécification de référence : **MASTER PROMPT V3**.
> Statut global : **PHASE 0 TERMINÉE — en attente de validation humaine
> avant PHASE 1.**

## 1. État initial (audit du repository existant)

La PHASE 0 demandait d'abord un audit du repository existant. Résultat :

- **Aucun repository n'existait** pour ce projet dans `~/workspace` avant
  le 24/11/2026 (vérifié : `ls ~/workspace/enterprise-infrastructure-intelligence`
  → *No such file or directory*).
- **Conclusion de l'audit : greenfield total.** Rien à auditer, rien à
  migrer, rien à supprimer. Le projet part de zéro.
- Toutes les décisions de la spécification V3 s'appliquent donc sans
  contrainte d'existant.

## 2. Ce qui existe (créé pendant la PHASE 0)

| Catégorie | Contenu |
|---|---|
| Structure | Arborescence complète §6 : `apps/`, `services/`, `packages/`, `infrastructure/`, `docs/`, `tests/`, `scripts/`, `.github/workflows/` |
| Documentation | `PRODUCT_REQUIREMENTS.md`, `SYSTEM_ARCHITECTURE.md`, `TECHNICAL_SPECIFICATION.md`, `DATABASE_DESIGN.md`, `API_SPECIFICATION.md`, `CONNECTOR_SPECIFICATION.md`, `SECURITY_ARCHITECTURE.md`, `THREAT_MODEL.md`, `AI_GOVERNANCE.md`, `ADR_INDEX.md` + 5 ADR, `BACKLOG.md`, `ACCEPTANCE_TESTS.md`, `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md` |
| Backend (squelette) | FastAPI : `app/main.py` (`/health`, `/api/v1/health`), config par `pydantic-settings`, session SQLAlchemy, routeurs, `requirements.txt`, tests pytest (`test_health.py`) |
| Frontend (squelette) | Next.js App Router : `package.json`, `tsconfig.json` (strict), Tailwind, `app/layout.tsx`, `app/page.tsx` (états chargement / vide / erreur, **aucune donnée fictive**), client API, composant `ui/button` (shadcn/ui) |
| Worker (squelette) | Celery : `celery_app.py`, tâche `healthcheck` (réelle, pas de fausse donnée) |
| Connecteur (squelette) | Connecteur de **simulation** : implémente le contrat commun, données marquées `simulated: true` partout, bannière SIMULATION |
| Types partagés | `packages/shared-types` : `Organization`, `User`, `Resource`, `Alert`, `Incident`, etc. |
| Docker | `docker-compose.yml` (PostgreSQL 16, Redis 7, api, worker, web, connector-sim) + 4 Dockerfiles sous `infrastructure/docker/` + `.dockerignore` |
| CI | `.github/workflows/ci.yml` : lint/typecheck/build web, lint/tests backend, scan secrets (gitleaks), validation `docker compose config` |
| Scripts | `scripts/check-env.sh` : vérification de l'environnement de dev |

## 3. Éléments validés (PHASE 0)

- [x] Structure du repository conforme à la §6 de la spécification.
- [x] Stack figée et documentée (ADR-0002) — aucune déviation.
- [x] Architecture Control Plane / Data Plane documentée (ADR-0001).
- [x] Modèle de données défini (§8 : 30+ entités, clés, index,
      contraintes, RLS envisagée — ADR-0005).
- [x] Contrats API `/api/v1` définis (conventions, erreurs, pagination,
      OpenAPI).
- [x] Contrat commun des connecteurs défini + connecteur de simulation.
- [x] Modèle de menace STRIDE rédigé.
- [x] Règles de gouvernance IA rédigées (module 10).
- [x] Backlog PHASE 1 priorisé (`BACKLOG.md`).
- [x] `docker-compose.yml` : syntaxe YAML validée (PyYAML 6.0.1).
- [x] Fichiers Python du squelette : syntaxe validée (`py_compile`).
- [x] `package.json` / `tsconfig.json` : JSON valides.
- [x] Workflow CI : YAML valide.
- [x] Backend squelette testé : pytest **3 passed**, `ruff check` OK,
      `ruff format --check` OK (après correction de `app/core/config.py`).
- [x] API squelette vérifiée en live (uvicorn local) : `/health` et
      `/api/v1/health` répondent, OpenAPI expose les 2 routes.
- [x] Connecteur de simulation exécuté : health ok, sync 3 ressources,
      2 métriques — tout marqué `simulated: true`.
- [x] Worker Celery vérifié : tâche `eii.healthcheck` exécutée en local.
- [x] Frontend squelette testé : `tsc --noEmit` 0 erreur, ESLint OK,
      `npm run build` réussi (Next.js 14.2.35, 4 pages statiques).
- [x] Aucun secret en clair dans le repository (vérifié par recherche
      de motifs `password|secret|token|api_key` hors placeholders
      documentés `change_me` / `${VAR}`).

## 4. Éléments manquants (à construire en PHASE 1+)

- Authentification OIDC réelle + RBAC (squelette uniquement, aucune
  session réelle en PHASE 0).
- Migrations Alembic (configuration présente, aucune migration créée).
- Tous les modules métier (dashboard, Infrastructure Manager, Proxmox,
  Linux, Monitoring, Alerting, Incidents, Automation, IA, Coûts,
  Rapports, Admin SaaS, Billing, site commercial).
- Connecteurs réels Proxmox / Debian / AWS (simulation uniquement).
- VictoriaMetrics / Prometheus (non déployés en PHASE 0).
- Tests d'isolation multi-tenant (squelettes seulement).
- Documentation : `OPERATIONS_GUIDE.md`, `COMPLIANCE_MATRIX.md`,
  `DEPLOYMENT_GUIDE.md`, `DATA_RETENTION_POLICY.md`, `DISASTER_RECOVERY.md`,
  `UX_SPECIFICATION.md` — à rédiger en PHASE 1 (listés §19).
- Aucun déploiement (dev, staging, production).

## 5. Vérification de l'environnement de dev (VM, 24/11/2026)

| Outil | Version observée | Statut |
|---|---|---|
| Node.js | v24.22.1 | ✅ (requis : 20+) |
| npm | 10.9.4 | ✅ |
| Python | 3.12.3 | ✅ (requis : 3.12) |
| pip | 24.0 | ✅ |
| git | 2.43.0 | ✅ |
| PyYAML | 6.0.1 | ✅ (validation YAML locale) |
| **Docker** | **absent (`command not found`)** | ❌ **ÉCART BLOQUANT pour le dev local** |
| podman | absent | — (alternative non installée) |

### Conséquences de l'écart Docker

- `docker compose up` **ne peut pas être exécuté sur cette VM** :
  l'environnement complet (Postgres, Redis, api, worker, web) n'a pas
  pu être démarré ni testé ici.
- Les Dockerfiles et `docker-compose.yml` sont rédigés et leur syntaxe
  est validée, mais **le build des images n'a pas été testé**.
- Vérifications locales effectuées à la place : `py_compile` (Python),
  validation YAML, `npm install` + `tsc --noEmit` (voir §6).
- **Action requise avant PHASE 1** : installer Docker Engine +
  Docker Compose sur la machine de développement (ou utiliser une VM /
  un poste équipé), puis exécuter `docker compose up --build` et
  consigner le résultat.

## 6. Tests exécutés (résultats réels, 24/11/2026)

| Test | Commande | Résultat |
|---|---|---|
| Syntaxe Python (squelettes) | `python3 -m py_compile` sur tous les `.py` | ✅ OK |
| Validation YAML compose | `yaml.safe_load(docker-compose.yml)` (PyYAML 6.0.1) | ✅ OK |
| Validation YAML CI | `yaml.safe_load(.github/workflows/ci.yml)` | ✅ OK |
| JSON web | `json.load` sur `package.json`, `tsconfig.json`, `.eslintrc.json` + 2 `package.json` de packages | ✅ OK |
| Recherche de secrets | `grep -R` motifs sensibles (hors placeholders) | ✅ aucun secret réel (uniquement `change_me_dev_only`) |
| `pytest` backend | venv `/tmp/eii-venv` + `pip install -r requirements.txt` + `pytest tests -q` | ✅ **3 passed** en 0,62 s (1 warning bénin : dépréciation pytest-asyncio + starlette BlockingPortal) |
| `ruff check` backend | `ruff check app tests` | ✅ All checks passed |
| `ruff format --check` backend | `ruff format --check app tests` | ✅ OK après reformatage de `app/core/config.py` (1 fichier corrigé, sans changement de comportement) |
| API live (uvicorn, port 8123) | `curl /health`, `/api/v1/health`, `/openapi.json` | ✅ `{"status":"ok"}` ; `{"status":"ok","api_version":"v1"}` ; OpenAPI liste les 2 routes |
| Connecteur de simulation | `python -m app.main` | ✅ Exécuté : health ok, sync 3 ressources vues/ajoutées, 2 métriques, tout marqué `simulated: true` |
| Worker Celery | import `celery_app` + `healthcheck.apply()` local | ✅ `{'status': 'ok', 'worker': 'eii_worker'}` |
| `npm install` (web) | `npm install` dans `apps/web` | ✅ Terminé (Next.js 14.2.35 installé) |
| `tsc --noEmit` (web) | `npx tsc --noEmit` | ✅ 0 erreur |
| `next lint` (web) | `npx next lint` | ✅ No ESLint warnings or errors |
| `npm run build` (web) | `npm run build` | ✅ Compiled successfully ; 4 pages statiques générées ; route `/` = 96,8 kB first load |
| `docker compose up --build` | — | ❌ **non exécutable : Docker absent de la VM** (voir §5) |
| CI GitHub Actions | — | ❌ **non exécutée : aucun dépôt distant** (workflow rédigé ; il tournera à la création du dépôt par Randy) |
| Tests e2e Playwright | — | ⏸️ Squelette présent, spec `dashboard.spec.ts` en `test.skip` (requiert web + api via docker compose) |
| Tests d'isolation multi-tenant | — | ⏸️ Squelette présent (`tests/security/test_tenant_isolation.py`, 2 tests `skip`, PHASE 1) |

## 7. Risques identifiés

| # | Risque | Gravité | Mitigation |
|---|---|---|---|
| R1 | Docker absent sur la VM de dev → l'environnement de référence n'est pas testé | **Haute** | Installer Docker avant PHASE 1 ; ne pas démarrer le MVP sans `docker compose up` vert |
| R2 | Périmètre très large (15 modules) → tentation de tout coder d'un coup | Haute | Phases strictes ; PHASE 1 = MVP seulement (voir BACKLOG.md) |
| R3 | Données simulées confondues avec des données réelles | Moyenne | Marquage `simulated: true` obligatoire ; UI : badge SIMULÉ ; interdiction de présenter la simulation comme réelle |
| R4 | Multi-tenancy ajouté après coup | Haute | Isolation dès la PHASE 1 (tests d'isolation obligatoires, RLS évaluée — ADR-0005) |
| R5 | Secrets / credentials Proxmox & AWS demandés trop largement | Moyenne | Comptes dédiés, permissions minimales, lecture seule d'abord (§7 modules 3-5) |
| R6 | IA avec accès libre à l'infrastructure | Haute | Moteur de politiques déterministe obligatoire avant toute action proposée par l'IA (AI_GOVERNANCE.md) |
| R7 | Conformité (RGPD, NIS2, SecNumCloud…) affirmée sans preuve | Moyenne | Ne jamais prétendre une certification ; matrice de conformité à rédiger en PHASE 1 |
| R8 | Dépendance aux fournisseurs IA externes (données clients) | Moyenne | Par défaut : pas d'entraînement sur données clients ; transmission minimisée et documentée |

## 8. Prochaines tâches (ordre)

1. **Validation humaine de cette PHASE 0** (ce document + docs + squelettes).
2. Installer Docker sur la machine de dev ; `docker compose up --build` vert.
3. PHASE 1 — MVP : auth OIDC + organisations + RBAC, dashboard,
   Infrastructure Manager, connecteur de simulation, connecteur Proxmox
   lecture seule, connecteur Debian lecture seule, Monitoring Center,
   audit de base, tests (voir `BACKLOG.md`).
4. Rédiger les documents manquants du §19 au fur et à mesure.

## 9. Statuts utilisés

`TODO` · `IN_PROGRESS` · `BLOCKED` · `IN_REVIEW` · `TESTED` · `ACCEPTED` ·
`DEPLOYED` — avec la distinction obligatoire : développé ≠ testé ≠
accepté ≠ déployé ≠ prêt pour la production.
