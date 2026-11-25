# PROJECT_STATUS.md — Enterprise Infrastructure Intelligence

> Dernière mise à jour : **25 novembre 2026, 23:58 CET** (revue GitHub des PR #2 à #12, de l'issue #1 et des runs CI #92, #98 et #104).
> Audit PHASE 0 : voir §10 — 81/81 fichiers vérifiés, CI verte (dernier run 4/4 jobs),
> 4 corrections (Dockerfiles COPY + `.dockerignore` + `npm ci` + harmonisation Worker) dans la PR `audit/phase-0`.
> Audit suite (instruction ChatGPT 25/11) : voir §11 — audit sécurité concret,
> validations CI manquantes ajoutées (build images + smoke test compose),
> corrections dans une PR distincte (non fusionnée).
> Spécification de référence : **MASTER PROMPT V3**.
> Statut global : **PHASE 0 en revue dans des PR ouvertes/non fusionnées ; PHASE 1 en cours avec P1-A0, P1-A1 et P1-A2 en PR ouvertes. Aucune acceptation produit ni aucun déploiement.**

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
| Docker | `docker-compose.yml` (PostgreSQL 16, Redis 7, api, worker, web, connector-sim) + 4 Dockerfiles sous `infrastructure/docker/` (COPY corrigés pour le contexte racine — audit §10 ; images non-root + healthchecks api/web/worker — audit suite §11) + `.dockerignore` (`.env.local` / `.env.*.local` exclus — §11) |
| CI | `.github/workflows/ci.yml` : lint/typecheck/build web, lint/tests backend, scan secrets (gitleaks), validation `docker compose config` **+ build des 4 images Docker + smoke test `compose up` (healthchecks) + audit de dépendances (report-only) — §11** |
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
      documentés `change_me` / `${VAR}` ; re-vérifié pendant l'audit).
- [x] CI GitHub Actions verte sur l'arborescence complète : dernier run
      (HEAD `076535c`) 4/4 jobs réussis (audit §10).
- [x] `docker compose config` validé (Compose v5.8.0, 24/11).
- [x] Fichiers annoncés vérifiés contre le dépôt réel : 81/81 présents
      (arborescence distante == fichiers locaux, audit §10).

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
| **Docker** | **29.1.3 + Compose v5.8.0** (installés le 24/11 23h10) | ✅ installé — ⚠️ daemon `dockerd --bridge=none --iptables=false` : bridge impossible dans cette VM (sandbox sans CAP_NET_ADMIN) |
| podman | absent | — (alternative non installée) |

### Limites Docker dans cette VM (audit du 24/11 au soir)

Docker est installé depuis le 24/11 23h10 (29.1.3 + Compose v5.8.0),
mais cette VM (sandbox) bloque la création de réseaux :

- `docker compose up` **ne peut pas être exécuté ici** : le daemon
  tourne avec `--bridge=none --iptables=false` (le sandbox refuse
  iptables/netlink, pas de CAP_NET_ADMIN) ; la création du réseau
  bridge de Compose échoue.
- Le **build des images n'a pas pu être testé ici** : le daemon ne
  parvient pas à joindre Docker Hub (`TLS handshake timeout` vers
  `registry-1.docker.io`, malgré un proxy fonctionnel en shell ;
  daemon redémarré avec un token proxy frais — même échec).
- En revanche, l'audit a trouvé et corrigé une **incohérence réelle**
  (voir §10) : les 4 Dockerfiles utilisaient des chemins COPY relatifs
  au dossier du service, alors que `docker-compose.yml` utilise le
  contexte racine — les builds auraient échoué à l'étape COPY.
- **Action requise avant PHASE 1** : exécuter
  `docker compose up --build` sur une machine avec un Docker complet
  (bridge fonctionnel + accès Docker Hub), puis consigner le résultat.
  La CI GitHub (dernier run vert) valide déjà lint/tests/build web/
  compose config à chaque push.

## 6. Tests exécutés (résultats réels, 24/11/2026 — re-exécutés à l'identique pendant l'audit du soir)

| Test | Commande | Résultat |
|---|---|---|
| Syntaxe Python (squelettes) | `python3 -m py_compile` sur tous les `.py` | ✅ OK |
| Validation YAML compose | `yaml.safe_load(docker-compose.yml)` (PyYAML 6.0.1) | ✅ OK |
| Validation YAML CI | `yaml.safe_load(.github/workflows/ci.yml)` | ✅ OK |
| JSON web | `json.load` sur `package.json`, `tsconfig.json`, `.eslintrc.json` + 2 `package.json` de packages | ✅ OK |
| Recherche de secrets | `grep -R` motifs sensibles (hors placeholders) | ✅ aucun secret réel (uniquement `change_me_dev_only`) |
| `pytest` backend | venv + `pip install -r requirements.txt` + `pytest tests -q` | ✅ **3 passed** en 0,49 s à l'audit (0,62 s en PHASE 0 ; 1 warning bénin : dépréciation pytest-asyncio + starlette BlockingPortal) |
| `ruff check` backend | `ruff check app tests` | ✅ All checks passed |
| `ruff format --check` backend | `ruff format --check app tests` | ✅ OK après reformatage de `app/core/config.py` (1 fichier corrigé, sans changement de comportement) |
| API live (uvicorn, port 8123) | `curl /health`, `/api/v1/health`, `/openapi.json` | ✅ `{"status":"ok"}` ; `{"status":"ok","api_version":"v1"}` ; OpenAPI liste les 2 routes |
| Connecteur de simulation | `python -m app.main` | ✅ Exécuté : health ok, sync 3 ressources vues/ajoutées, 2 métriques, tout marqué `simulated: true` |
| Worker Celery | import `celery_app` + `healthcheck.apply()` local | ✅ `{'status': 'ok', 'worker': 'eii_worker'}` |
| `npm install` (web) | `npm install` dans `apps/web` | ✅ Terminé (Next.js 14.2.35 installé) |
| `tsc --noEmit` (web) | `npx tsc --noEmit` | ✅ 0 erreur |
| `next lint` (web) | `npx next lint` | ✅ No ESLint warnings or errors |
| `npm run build` (web) | `npm run build` | ✅ Compiled successfully ; 4 pages statiques générées ; route `/` = 96,8 kB first load |
| `docker compose up --build` | — | ❌ **non exécutable dans cette VM** : pas de réseau bridge (sandbox, voir §5) — à exécuter sur une machine Docker normale |
| Build des images Docker | `docker build --network=host` (api) | ❌ **non testé** : pull Docker Hub impossible depuis le daemon de cette VM (`TLS handshake timeout` vers `registry-1.docker.io`) |
| `docker compose config` | `docker compose config --quiet` (Compose v5.8.0) | ✅ OK — fichier valide, chemins des 4 Dockerfiles résolus |
| CI GitHub Actions | 33 runs sur main (API GitHub) | ✅ **exécutée** : runs 1–29 en échec (arborescence incomplète pendant le téléversement par lots) ; runs 30–33 **succès** ; dernier run (HEAD `076535c`) 4/4 jobs verts (gitleaks, API, Web, Compose) |
| Audit fichiers vs dépôt | arborescence distante (API GitHub) vs fichiers locaux | ✅ **81/81 fichiers présents**, identiques, HEAD `076535c` |
| Dockerfiles vs compose | lecture des 4 Dockerfiles + `docker-compose.yml` | ❌ **incohérence trouvée** : COPY relatifs au dossier du service vs contexte racine — corrigée dans la PR d'audit (voir §10) |
| Tests e2e Playwright | — | ⏸️ Squelette présent, spec `dashboard.spec.ts` en `test.skip` (requiert web + api via docker compose) |
| Tests d'isolation multi-tenant | — | ⏸️ Squelette présent (`tests/security/test_tenant_isolation.py`, 2 tests `skip`, PHASE 1) |

## 7. Risques identifiés

| # | Risque | Gravité | Mitigation |
|---|---|---|---|
| R1 | `docker compose up` non testé (VM sandbox sans bridge ; pull Hub impossible) → l'environnement de référence n'est pas testé de bout en bout | **Haute** | Docker installé le 24/11 ; valider `docker compose up --build` sur une machine Docker normale avant de démarrer le MVP |
| R2 | Périmètre très large (15 modules) → tentation de tout coder d'un coup | Haute | Phases strictes ; PHASE 1 = MVP seulement (voir BACKLOG.md) |
| R3 | Données simulées confondues avec des données réelles | Moyenne | Marquage `simulated: true` obligatoire ; UI : badge SIMULÉ ; interdiction de présenter la simulation comme réelle |
| R4 | Multi-tenancy ajouté après coup | Haute | Isolation dès la PHASE 1 (tests d'isolation obligatoires, RLS évaluée — ADR-0005) |
| R5 | Secrets / credentials Proxmox & AWS demandés trop largement | Moyenne | Comptes dédiés, permissions minimales, lecture seule d'abord (§7 modules 3-5) |
| R6 | IA avec accès libre à l'infrastructure | Haute | Moteur de politiques déterministe obligatoire avant toute action proposée par l'IA (AI_GOVERNANCE.md) |
| R7 | Conformité (RGPD, NIS2, SecNumCloud…) affirmée sans preuve | Moyenne | Ne jamais prétendre une certification ; matrice de conformité à rédiger en PHASE 1 |
| R8 | Dépendance aux fournisseurs IA externes (données clients) | Moyenne | Par défaut : pas d'entraînement sur données clients ; transmission minimisée et documentée |

## 8. Prochaines tâches (ordre)

1. **Validation humaine de cet audit PHASE 0** (PR `audit/phase-0` :
   corrections Dockerfiles + `.dockerignore` + ce document + `BACKLOG.md`).
2. `docker compose up --build` vert sur une machine Docker normale
   (Docker déjà installé sur la VM d'audit ; non testable ici, voir §5).
3. PHASE 1 — MVP : auth OIDC + organisations + RBAC, dashboard,
   Infrastructure Manager, connecteur de simulation, connecteur Proxmox
   lecture seule, connecteur Debian lecture seule, Monitoring Center,
   audit de base, tests (voir `BACKLOG.md`).
4. Rédiger les documents manquants du §19 au fur et à mesure.

## 9. Statuts utilisés

`TODO` · `IN_PROGRESS` · `BLOCKED` · `IN_REVIEW` · `TESTED` · `ACCEPTED` ·
`DEPLOYED` — avec la distinction obligatoire : développé ≠ testé ≠
accepté ≠ déployé ≠ prêt pour la production.

## 10. Résultats de l'audit PHASE 0 (24/11/2026, soir)

Audit ordonné avant toute PHASE 1. Méthode : arborescence distante via
l'API GitHub, re-exécution locale de tous les tests, lecture des 4
Dockerfiles et de `docker-compose.yml`, analyse des 33 runs CI.

| # | Point audité | Résultat |
|---|---|---|
| 1 | Fichiers annoncés vs dépôt réel | ✅ 81/81 présents, identiques aux fichiers locaux (HEAD `076535c`) |
| 2 | Cohérence PROJECT_STATUS.md / BACKLOG.md | ❌ 7 affirmations obsolètes corrigées (Docker, CI, P1-01, nom personnel) |
| 3 | GitHub Actions | ✅ dernier run 4/4 jobs verts ; 29 premiers runs en échec expliqués (arborescence incomplète pendant le téléversement) |
| 4 | Dockerfiles / compose | ❌ COPY incompatibles avec le contexte racine — corrigés (voir ci-dessous) |
| 5 | Présence frontend / backend / worker / connecteur | ✅ tous présents (fichiers clés vérifiés un par un) |
| 6 | Tests déclarés | ✅ tous re-exécutés pendant l'audit, résultats identiques |

### Corrections appliquées (PR `audit/phase-0`)

1. **4 Dockerfiles** (`infrastructure/docker/`) : chemins COPY rendus
   relatifs à la racine du dépôt (contexte de `docker-compose.yml`).
   Avant, `COPY requirements.txt .` / `COPY app ./app` /
   `COPY package.json ...` / `COPY . .` supposaient le dossier du
   service comme contexte — ces fichiers n'existent pas à la racine,
   les builds auraient échoué à l'étape COPY.
2. **`.dockerignore`** : `node_modules` → `**/node_modules`,
   `.next` → `**/.next` (les motifs sans `**/` ne s'appliquent qu'à
   la racine ; le contexte de build envoyé mesurait 409,6 Mo, soit
   `apps/web/node_modules` presque entier).
3. **Ce document (§5, §6, §7, §8)** : Docker installé, CI exécutée et
   verte, cause réelle de l'impossibilité de `compose up`, retrait du
   nom personnel (dépôt désormais public).
4. **`BACKLOG.md`** : Docker et CI passés à leurs statuts réels,
   P1-01 reformulée (Docker installé ; reste `compose up` à valider).

### Round 2 — revue technique indépendante (25/11/2026)

Revue de Randy : CI verte (4/4 jobs), 2 points corrigés dans la PR :

1. **`web.Dockerfile` : `npm install` → `npm ci`** (installation reproductible, lockfile désormais obligatoire). Vérifié localement : `npm ci` exit 0 (435 packages, 24 s), puis `npm run build` OK.
2. **Worker : commande de démarrage harmonisée.** `docker-compose.yml` surchargeait avec `celery -A app.celery_app worker`, le CMD de l'image dit `celery -A app.celery_app.celery_app worker`. **Les deux formes ont été testées en live : elles démarrent le worker avec la bonne application `eii_worker`** (la forme courte marche via le balayage d'instance de Celery 5.4, mais elle est implicite). Retenu : la forme explicite comme seule source de vérité (CMD de l'image) ; le `command:` est retiré de `docker-compose.yml`. `docker compose config` OK après la modification.

Autres vérifications du 25/11 : chemins COPY des 4 Dockerfiles tous existants ; tests locaux re-exécutés (pytest 3 passed, ruff OK, tsc 0, build web OK, API live OK, sim OK, worker OK).

### Non testé (honnêtement)

- Build des images Docker : pull Docker Hub impossible depuis le daemon
  de cette VM (`TLS handshake timeout`).
- `docker compose up --build` : pas de réseau bridge dans cette VM
  (sandbox sans CAP_NET_ADMIN).
- Les deux sont à valider sur une machine Docker normale ou via la CI
  (qui tourne déjà à chaque push).
- **Précisions du 25/11 :** la VM a été remplacée entre le 24/11 et le 25/11 (Docker avait disparu) ; Docker 29.1.3 + Compose v5.8.0 réinstallés le 25/11, daemon `--bridge=none --iptables=false`. Build `api` tenté le 25/11 : échec étape 1/10 (pull `python:3.12-slim`, TLS handshake timeout vers `registry-1.docker.io`). **Mesure directe :** contexte de build **568,5 Mo** avec l'ancien `.dockerignore` contre **572,9 kB** avec le corrigé (~1000× de moins).

## 11. Audit suite — instruction ChatGPT du 25/11 (PR #2)

Audit ordonné par ChatGPT (commentaire PR #2, 25/11 10h41, via ChatGPT Codex
Connector) : vérifier l'état réel de la PR et de `main`, ajouter les
validations CI manquantes, compléter `.dockerignore`, vérifier versions et
dépendances, produire un audit sécurité concret, publier les résultats ici et
dans `BACKLOG.md`, ouvrir une **PR distincte** pour les corrections (sans
fusionner dans `main`). Rapport complet :
`docs/security/SECURITY_AUDIT_2026-11-25.md`.

### État réel vérifié

- **PR #2 : Open, non fusionnée** — 6 commits, tête `ec7c797`, base `main`
  `076535c`, `mergeable_state: clean`. **Main HEAD : `076535c`** (« Phase 0 :
  fondations — worker Celery », 24/11 22h05).
- **Écarts relevés dans la description de la PR #2** (à corriger avant fusion) :
  « PYTHONPATH corrigé » — faux (zéro occurrence de `PYTHONPATH` dans le code,
  le diff ne change que les COPY) ; « GET /v1/assets, POST /v1/simulate 200 » —
  faux (l'API n'expose que `GET /health` et `GET /api/v1/health`) ;
  chemins de tests inexacts (le seul fichier est
  `apps/api/tests/test_health.py`, 3 tests — le nombre est correct, les chemins
  non) ; affirmation sur `.dockerignore` inexacte (les motifs existaient déjà
  à la racine, le problème était l'absence de `**/`).

### Corrections apportées (PR distincte, non fusionnée)

1. **CI — job `docker-build`** : build des 4 images Docker à chaque push/PR
   (les builds n'avaient jamais été exécutés nulle part ; les runners GitHub
   ont un accès Docker Hub complet, contrairement à cette VM).
2. **CI — job `compose-smoke`** : `docker compose up -d --build`, attente des
   healthchecks api/web/worker, vérification `GET /health`, `GET /` web,
   `celery inspect ping`, exit code 0 du connecteur-sim (one-shot), puis
   `docker compose down -v`.
3. **CI — job `security-audit` (report-only)** : `pip-audit` sur les 4 fichiers
   de requirements + `npm audit --audit-level=high` (en `continue-on-error` :
   les vulnérabilités connues sont signalées sans bloquer la PR — les
   corrections sont planifiées, voir ci-dessous).
   **Correctif déclencheur (25/11 11h04) :** la PR #3 n'avait AUCUN check car
   le workflow ne se déclenchait que sur main/develop — `pull_request:` est
   désormais sans filtre de branche (toute PR obtient la CI).
4. **Conteneurs non-root** : `USER app` (images Python) / `USER node` (web),
   vérifié en CI (`id -u` ≠ 0 pour les 4 images).
5. **`--reload` retiré** du CMD de l'image API (outil de dev, pas dans l'image
   livrée).
6. **Healthchecks ajoutés** : api (`/health` via urllib), web (`/` via wget),
   worker (`celery inspect ping`) ; `connector-sim` exempté (one-shot, exit 0).
7. **`.dockerignore`** : `.env.local` et `.env.*.local` ajoutés
   (`.env.example` reste inclus).
8. **Split des requirements API** : `requirements.txt` = exécution uniquement
   (pytest/ruff déplacés vers `requirements-dev.txt`) — l'image Docker ne
   contient plus les outils de dev.

### Audit sécurité (résumé — détail dans `docs/security/SECURITY_AUDIT_2026-11-25.md`)

- **Secrets :** aucun secret réel (gitleaks vert, grep vérifié) ; placeholders
  dev uniquement ; `.env` exclu du contexte ; aucun vrai `.env` dans le dépôt.
- **Dépendances Python (`pip-audit`, 25/11) : 8 vulnérabilités uniques** —
  starlette 0.41.3 (7, transitive de FastAPI 0.115.6 qui exige
  `starlette<0.42.0`) et pytest 8.3.4 (1, dev-only). Surface exploitable
  actuelle limitée (2 endpoints health) ; correction = montée FastAPI à
  planifier en lot dédié (pas de patch silencieux). Worker + connecteur :
  aucune vulnérabilité connue.
- **Smoke test compose :** run #39 : worker sorti avec le code 1, cause
  inconnue (le script mourait avant d'afficher les logs) ; run #42 :
  **cause trouvée — `ModuleNotFoundError: No module named 'packaging'`**
  (le transport Redis de kombu importe `packaging.version`, paquet absent de
  l'image worker). **Correctif : `packaging==26.4` ajouté à
  `services/worker/requirements.txt` et `apps/api/requirements.txt`**
  (l'API installe aussi Celery) ; reproduit et vérifié en local dans un venv
  propre (sans packaging → même erreur ; avec → worker prêt). Run #46 :
  packaging validé (worker démarre, tâche enregistrée) mais **nouvel échec :
  `kombu.exceptions.VersionMismatch` — le transport Redis exige redis-py
  >= 6.1.0, le projet épinglait 5.2.1**. **Correctif : `redis==6.1.0`**
  (minimum exigé, 0 vulnérabilité connue per pip-audit) dans les deux
  requirements ; vérifié en local (5.2.1 → VersionMismatch ; 6.1.0 → la
  porte de version passe, seule erreur = pas de serveur Redis local, normal).
  Nouveau run CI en attente.
- **Dépendances Node :** `npm audit` **exécuté en CI** (run #39, PR #3,
  25/11 11h06) : **7 vulnérabilités (1 moderate, 5 high, 1 critical)** —
  glob (high), minimatch (moderate), next ≤ 16.3.0-preview.10 (**critical**,
  26 avis dont RCE non authentifiée), postcss ≤ 8.5.22 (high), zod < 4.6.6
  (high) ; correctifs = breaking changes (next 16.4.6, zod 4.6.7) — montée
  majeure à planifier en lot dédié, pas de patch silencieux. `npm outdated` :
  aucune dépendance en retard dans les plages déclarées.
- **Versions :** Python 3.12, Node 20 (LTS jusqu'en avril 2026 — passage en
  Node 22 à planifier ; ESLint 8 en fin de vie).
- **Authentification / isolation multi-tenant / journal d'audit : non
  implémentés** (par conception, PHASE 0) — contrôles à construire en PHASE 1
  (P1-02, P1-04, P1-14, P1-12), pas des failles présentes.
- **CORS :** restrictif par défaut (`localhost:3000`), `allow_credentials=True`
  à surveiller à chaque origine ajoutée. **CSRF :** non applicable (pas de
  sessions). **Entrées :** les 2 endpoints ne prennent aucun paramètre.
  **Logs :** défaut uvicorn, aucun secret vérifié. **`/docs` et
  `/openapi.json`** exposés (dev OK, à restreindre avant exposition publique).
  **Ports 5432/6379/8000/3000** désormais liés à `127.0.0.1` ; assertion CI active (run #54).

### Limites explicites

- Le build des 4 images et le smoke test `compose up` sont désormais
  **validés par la CI GitHub (run #54)** : les services démarrent et passent
  leurs healthchecks. La VM d'audit locale conserve ses limites réseau ; la
  confirmation sur le poste de développement reste à consigner (P1-01).
- `npm audit` reste bloqué localement par le proxy, mais a été exécuté en CI
  (run #54) : 7 vulnérabilités détectées ; le job reste report-only.
- Le runtime Web Node 22 est migré et testé (run #54). La montée Next 16 /
  React 19 / ESLint 10 et la montée FastAPI/Starlette restent des lots dédiés,
  à exécuter avec re-tests et sans mise à niveau majeure automatique.


## 12. Revalidation de la revue — 25/11/2026

**HEAD vérifié :** `15ad9b9050c1fe08687e8d7cc47a6a4f756426d4` — **CI run #54**.

- **Compose / ports :** DB 5432, Redis 6379, API 8000 et Web 3000 sont publiés uniquement sur `127.0.0.1`. Le job `compose-validate` vérifie automatiquement le JSON rendu et confirme cette contrainte.
- **Node 22 :** `infrastructure/docker/web.Dockerfile` utilise `node:22-alpine` dans ses trois stages ; les deux jobs `setup-node` utilisent Node 22. `npm ci`, lint, typecheck, build Web et build de l'image Web réussis.
- **Images Docker :** les quatre images sont construites ; contrôle non-root réussi (API uid 999, Web uid 1000, Worker uid 999, connecteur uid 999).
- **Compose smoke :** API, Web et Worker healthy ; endpoints API/Web vérifiés ; connecteur de simulation terminé avec exit code 0 ; ports hôte observés sur 127.0.0.1.
- **API / secrets :** lint, format, pytest et gitleaks réussis.
- **Audit dépendances :** job report-only terminé avec succès, mais les commandes d'audit ont trouvé des vulnérabilités : pip-audit 16 occurrences / 8 avis uniques (Starlette 0.41.3, pytest 8.3.4) ; npm audit 7 vulnérabilités (1 moderate, 5 high, 1 critical). Les étapes restent en `continue-on-error: true` ; le statut vert ne signifie pas absence de vulnérabilités.
- **PR #2 :** description corrigée pour retirer les affirmations non vérifiées. PR #2 et PR #3 restent ouvertes et non fusionnées.
- **Avertissement CI restant :** les actions GitHub `checkout@v4`, `setup-node@v4` et `setup-python@v5` émettent encore un avertissement de runtime Node 20 forcé vers Node 24. Le runtime applicatif Web est bien Node 22.

### Suite proposée

1. Mettre à niveau FastAPI/Starlette dans un lot dédié avec tests de compatibilité.
2. Mettre à jour les versions des actions GitHub dans un lot CI séparé.
3. Préparer Phase 1 par sous-lots : migrations Alembic, organisations/membres, sessions/OIDC, RBAC, isolation multi-tenant, audit log.
4. La validation Compose sur un poste de développement Docker normal reste à consigner ; la CI hébergée a validé le build et le smoke test.


## 13. Phase 1 — P1-A0 Fondation Alembic (25/11/2026)

**PR #4 :** https://github.com/BVDMANN/enterprise-infrastructure-intelligence/pull/4  
**Branche :** `phase1/p1-a0-alembic-foundation` (empilée sur PR #3)  
**Run CI #64 :** tous les jobs sont terminés avec succès ; le job de dépendances reste report-only. Le run #64 revalide aussi le cycle Alembic upgrade → downgrade base → nouvel upgrade sur PostgreSQL 16.

- Révision initiale `0001_pg_extensions` ajoutée : installe `citext`, sans table métier.
- `env.py` compare les types lors des migrations offline/online.
- Deux tests structurels Alembic ajoutés ; résultat API : **5 passed, 1 warning** (avertissement de configuration pytest-asyncio).
- Smoke PostgreSQL 16 : `alembic upgrade head` → `0001_pg_extensions (head)`, extension `citext` présente, `alembic downgrade base`, nouvel upgrade vers `head` — réussite.
- Le downgrade conserve volontairement l'extension PostgreSQL partagée pour éviter de la supprimer si d'autres objets l'utilisent.
- Les quatre images Docker, le build Web Node 22, Compose smoke, gitleaks et la validation des ports loopback sont verts.
- Aucun endpoint métier, table d'organisation, mécanisme d'authentification ou secret réel n'a été ajouté.

**Statut :** PR #4 est ouverte, non-draft et non fusionnée (état GitHub vérifié). Elle est prête pour revue. Prochain sous-lot prévu : P1-A1 organisations, utilisateurs et memberships, avec contraintes d'unicité et tests négatifs avant toute route métier.

## 14. Phase 1 — P1-A1 Organisations, utilisateurs et memberships (25/11/2026)

**Branche :** `phase1/p1-a1-organisations-utilisateurs` (empilée sur `phase1/p1-a0-alembic-foundation`, PR #4)  
**PR :** #5 (https://github.com/BVDMANN/enterprise-infrastructure-intelligence/pull/5), empilée sur PR #4 — ouverte, non fusionnée.

- Modèles SQLAlchemy 2 ajoutés (`app/models/identity.py`) : `organizations` (UUID, nom, slug unique, timestamps, soft delete), `users` (UUID, email CITEXT normalisé/unique, display_name, oidc_subject unique nullable, mfa_enabled, is_active, soft delete), `memberships` (UUID, organisation + utilisateur + rôle, unicité (organization_id, user_id), CHECK rôle owner/admin/member/viewer, FK RESTRICT).
- Migration `0002_identity` (révision `0002_identity`, parent `0001_pg_extensions`) : crée les trois tables, contraintes et index ; downgrade les supprime dans l'ordre inverse.
- `env.py` importe désormais `app.models` : `Base.metadata` reflète les tables réelles (vérifié par `alembic check` sans dérive sur PostgreSQL 16 local).
- Lectures limitées au membership (`app/services/identity.py`) : un utilisateur sans membership ne voit aucune organisation ; une organisation d'un autre tenant n'est jamais retournée ; les organisations soft-deleted sont exclues. Aucune route HTTP n'est ouverte par ce lot.
- Tests API : **30 passed, 1 warning** (avertissement pytest-asyncio préexistant) — 25 nouveaux tests (18 modèles, 5 service, 2 migration) : unicité slug/email/membership, normalisation, FK, CHECK rôle, soft delete, RESTRICT, visibilité par membership, graphe de migration linéaire 0001 → 0002.
- Vérification PostgreSQL 16 locale (hors CI) : `alembic upgrade head` → `0002_identity (head)`, `alembic check` sans dérive, 20/20 contrôles (dont CITEXT rejetant un email en casse différente au niveau base, downgrade base puis nouvel upgrade) — réussite.
- CI : le smoke Compose vérifie désormais aussi la présence des trois tables après `alembic upgrade head`.
- Aucun endpoint métier, mécanisme d'authentification ou secret réel n'a été ajouté.

**Statut :** lot livré, PR #5 ouverte. Prochain sous-lot : P1-A2 sessions et OIDC.


## 12. Revue de pilotage — 25/11/2026, 23:23 CET

Cette section remplace les anciens instantanés de statut des sections précédentes lorsqu'ils divergent des états GitHub ci-dessous. Contrôle effectué sur les PR, branches, commits, commentaires, revues et runs accessibles.

### État des Pull Requests

| PR | Branche | Base | Tête | Validation CI observée | État |
|---|---|---|---|---|---|
| #2 | `audit/phase-0` | `main` | `ec7c797` | Dernier état historique décrit dans la PR ; pas de nouvelle preuve de run sur cette tête dans ce contrôle | Ouverte, non fusionnée |
| #3 | `audit/phase-0-followup` | PR #2 | `b916147` | Run #59 annoncé réussi dans la PR | Ouverte, non fusionnée |
| #4 | `phase1/p1-a0-alembic-foundation` | PR #3 | `3b13af0` | Run #67 : 7/7 jobs réussis | Ouverte, non fusionnée |
| #5 | `phase1/p1-a1-organisations-utilisateurs` | PR #4 | `5a6baea` | Run #73 : 7/7 jobs réussis | Ouverte, non fusionnée |
| #6 | `phase1/demo-ui-shell` | PR #5 | `c054606` | Run #74 : 7/7 jobs réussis | Ouverte, non fusionnée |
| #7 | `phase1/ci-node24-actions` | PR #5 | `f5475b3` | Run #77 : 7/7 jobs réussis | Ouverte, non fusionnée |
| #8 | `phase1/p1-a1-active-user-filter` | PR #5 | `65d51bb` | Run #76 : 7/7 jobs réussis | Ouverte, non fusionnée |

Les comparaisons GitHub confirment que les têtes des PR #6, #7 et #8 incluent la tête P1-A1 de la PR #5 : respectivement 18, 3 et 2 commits en avance, sans commit manquant par rapport à cette base. Les huit branches visibles sont `main`, les deux branches `audit/*`, puis les branches P1-A0, P1-A1, correctif utilisateur actif, UI et actions Node 24.

### État produit vérifié

- **P1-A0 :** migration `0001_pg_extensions` présente ; elle installe `citext` uniquement. La PR #4 reste ouverte. Le downgrade conserve volontairement l'extension partagée.
- **P1-A1 :** modèles organisations/utilisateurs/memberships et migration `0002_identity` présents dans la PR #5. Aucune route HTTP d'identité n'est encore ouverte.
- **Correctif de lecture P1-A1 :** PR #8 ajoute les filtres `is_active IS TRUE` et `deleted_at IS NULL` dans les deux helpers et deux tests négatifs ; API CI : 32 tests réussis.
- **P1-A2 :** non implémenté. Le point d'entrée FastAPI expose encore les sondes de santé uniquement ; aucune session, route login/logout ou intégration OIDC réelle n'est revendiquée.
- **Interface :** PR #6 ajoute les pages Dashboard, Organisations, Utilisateurs, Infrastructure et Audit. Les données métier sont explicitement fictives ; seul le healthcheck du Control Plane appelle l'API réelle.
- **Actions CI :** PR #7 migre checkout vers v7.0.1, setup-node vers v7.1.0, setup-python vers v7.1.0 et Gitleaks vers v3. Les sept logs du run #77 ne contiennent aucun avertissement « Node.js 20 is deprecated ». Gitleaks émet encore DEP0040 (punycode) et DEP0169 (url.parse).
- **Branches non migrées :** le run #76 de la PR #8 utilise encore les anciennes actions héritées de sa base P1-A1 ; au moins un log affiche l'avertissement Node 20. La PR #7 reste séparée et non fusionnée.

### Risques et limites

- Audit Python report-only, run #77 : 16 occurrences de vulnérabilités dans 2 paquets — pytest 8.3.4 et Starlette 0.41.3 — correspondant à 8 avis uniques.
- Audit npm report-only, run #77 : 7 vulnérabilités — 1 modérée, 5 élevées, 1 critique. Les étapes d'audit restent visibles et ne sont pas considérées comme une validation de sécurité.
- La confirmation de `docker compose up --build` sur un poste développeur normal reste à consigner ; la CI hébergée exécute déjà le build des images et le smoke Compose.
- Aucun merge, déploiement, ajout de secret ou changement de permission sensible n'a été réalisé.

### Coordination

Au contrôle du 25/11 à 23:58, les PR #2 à #12, l'issue #1, les commentaires/révisions consultés, les branches visibles et les recherches de commits `author:Ruby` / `committer:Ruby` ne fournissent aucune preuve attribuable à Ruby. Les PR visibles sont publiées sous le compte `BVDMANN`, ce qui ne suffit pas à attribuer un travail à Ruby. Aucune contribution ne lui est attribuée sans preuve vérifiable.


## 12. Actualisation du pilotage — 25/11/2026, 23:58 CET

Cette section remplace les statuts opérationnels du snapshot §11 daté de 23:23 ; les anciennes observations restent conservées comme historique.

| Lot | Statut vérifié | Preuve et limite |
|---|---|---|
| Phase 0 — PR #2 à #4 | IN_REVIEW | PR ouvertes, non fusionnées. La description de #2 est corrigée ; #3 conserve les audits report-only. La confirmation `docker compose up --build` sur le poste développeur reste attendue, même si les smoke tests CI passent. |
| P1-A0 | IN_REVIEW / TESTED | PR #4, migration `0001_pg_extensions`, run #67 : 7/7 jobs réussis ; cycle PostgreSQL upgrade/downgrade/upgrade vérifié. |
| P1-A1 | IN_REVIEW / TESTED | PR #5 (run #73) et PR #8 (run #76, 32 tests API) : modèles et lectures membership-scoped. Aucune route HTTP d'organisation ou d'identité n'est livrée par ces lots. |
| Interface de démonstration | IN_REVIEW / DEMO | PR #6, run #74 : pages Dashboard, Organisations, Utilisateurs, Infrastructure et Audit navigables ; données métier simulées, seul le healthcheck API est réel. |
| Actions GitHub Node 24 | IN_REVIEW / TESTED | PR #7, run #77 : 7/7 jobs réussis, actions checkout/setup-node/setup-python mises à jour. Les branches non empilées sur #7 peuvent encore afficher les avertissements Node 20. Le runtime applicatif Web Node 22 reste distinct et validé. |
| P1-A2.1 — sessions serveur | IN_REVIEW / TESTED | PR #10, tête `fff99f4`, run #92 : 7/7 jobs réussis. Sessions opaques, hashées, expirables et révocables ; PR ouverte, non fusionnée. |
| P1-A2.2 — authentification locale | IN_REVIEW / TESTED | PR #11, draft, tête `acb12af`. Argon2id, login/me/logout, cookies HttpOnly et CSRF présents dans la branche. Run #104 : 7/7 jobs réussis ; API 55 tests passés, 1 avertissement. Le job d'audit reste report-only et signale 16 occurrences Python + 7 vulnérabilités npm. Aucun OIDC provider ni challenge MFA n'est livré. |
| P1-A2.3 — OIDC / MFA | TODO | Validation issuer/audience/signature/nonce/state et flux MFA à implémenter ; un compte avec MFA activée est refusé au login local, sans second facteur disponible à ce stade. |
| P1-A3 — RBAC | TODO | `memberships.role` reste une chaîne avec CHECK ; permissions serveur et matrice d'autorisation non implémentées. |
| P1-A4 — isolation multi-tenant | TODO / SOCLE PARTIEL | Les helpers P1-A1 filtrent par membership, utilisateur actif et soft-delete ; pas encore de contexte tenant dérivé d'une session, de routes métier ni de RLS. |
| P1-A5 — audit trail | TODO | Aucun journal métier append-only implémenté. |
| Dépendances Python | IN_REVIEW / TESTED | PR #12, run #98 : 7/7 jobs réussis ; `pip-audit` indique « No known vulnerabilities found ». Le commit `8b1e157` ajoute `httpx2==2.16.2` pour le TestClient Starlette ; run #107 en cours, job API vert et sans avertissement Starlette/TestClient dans ses logs. PR ouverte, non fusionnée. |
| Dépendances npm | TODO / REPORT-ONLY | 7 vulnérabilités (1 modérée, 5 élevées, 1 critique) : `next` critique, `glob`/`postcss` élevés, `zod` élevé et `minimatch` modéré. `npm audit fix --force` propose Next 16.4.6 et Zod 4.6.7 (breaking changes) ; aucune mise à niveau majeure aveugle. L'étape sort en erreur mais reste `continue-on-error` ; job vert ≠ audit propre. |

### Coordination des dépendances et limites

- PR #11 ajoute `argon2-cffi==25.1.0` dans `apps/api/requirements.txt`, tandis que PR #12 met à niveau FastAPI dans ce même fichier et pytest/pytest-asyncio dans `requirements-dev.txt`. La résolution combinée doit conserver les deux apports et être revalidée après synchronisation ; aucune fusion automatique n'a été effectuée.
- Le run #104 de la PR #11 est terminé 7/7 ; ses logs montrent encore `checkout@v4` et `setup-python@v5` (avertissement runtime Node 20). La migration Node 24 de la PR #7 n'est pas encore intégrée à toutes les branches.
- Le run #106 de cette PR documentaire est terminé 7/7 sur la tête `0cfab788`.
- Aucun merge, déploiement, ajout de secret réel, changement de permission sensible ou suppression n'a été réalisé.
