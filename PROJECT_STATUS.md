# PROJECT_STATUS.md — Enterprise Infrastructure Intelligence

> Dernière mise à jour : **25 novembre 2026** (audit PHASE 0 + round 2 + audit suite ChatGPT).
> Audit PHASE 0 : voir §10 — 81/81 fichiers vérifiés, CI verte (dernier run 4/4 jobs),
> 4 corrections (Dockerfiles COPY + `.dockerignore` + `npm ci` + harmonisation Worker) dans la PR `audit/phase-0`.
> Audit suite (instruction ChatGPT 25/11) : voir §11 — audit sécurité concret,
> validations CI manquantes ajoutées (build images + smoke test compose),
> corrections dans une PR distincte (non fusionnée).
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
  propre (sans packaging → même erreur ; avec → worker prêt). Nouveau run CI
  en attente.
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
  **Ports 5432/6379** exposés en dev local (à retirer avant déploiement exposé).

### Limites explicites

- Le build des images et le smoke test `compose up` **n'ont pas pu être
  exécutés dans cette VM** (pull Docker Hub en TLS timeout, pas de bridge) —
  ils seront validés par la CI de la PR distincte (runners GitHub) et restent
  à confirmer sur une machine Docker normale (P1-01).
- `npm audit` n'a pas pu être exécuté localement (proxy) — première exécution
  attendue en CI.
- La montée FastAPI (starlette) et la montée Node 22 / Next 16 ne sont **pas**
  effectuées ici : lots dédiés à planifier, avec re-tests.
