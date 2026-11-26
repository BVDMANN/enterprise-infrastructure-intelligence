# Audit sécurité — Enterprise Infrastructure Intelligence

> **Date :** 25 novembre 2026 — **Périmètre :** PHASE 0, PR #2 (`audit/phase-0`) + PR #3 (`audit/phase-0-followup`), HEAD analysé `15ad9b9` (run CI #54, 19:09 UTC).
> **Auteur vérifié du rapport dans Git :** BVDMANN (commit `321dea311a87e222fa8dd00cbb068f70c2e8265d`, committer et auteur BVDMANN). Aucune contribution de Ruby n'est attribuée dans ce rapport : aucune PR, aucun commit ni commentaire Ruby vérifiable n'a été retrouvé dans ce dépôt au contrôle du 26/11/2026.
> **Méthode :** lecture du code, des Dockerfiles, de Compose, de `.dockerignore` et de la CI ; tests locaux antérieurs ; inspection des logs du run CI #54 sur le commit `15ad9b9` (25/11, 19:09–19:11 UTC).
> **Audit dépendances :** `pip-audit` et `npm audit --audit-level=high` exécutés en CI. Les deux commandes ont retourné le code 1 en raison de vulnérabilités ; les étapes restent volontairement `continue-on-error: true` et le job est report-only. Un job vert ne signifie donc pas zéro vulnérabilité.
> **Règle :** aucune affirmation sans preuve ; ce qui n'est pas vérifiable est
> signalé comme tel. Aucun secret réel n'a été ajouté, lu ou exposé.

## 0. Résumé

| Verdict | Détail |
|---|---|
| **Aucun secret réel** dans le dépôt (gitleaks vert en CI, grep vérifié) | Placeholders `change_me_dev_only` uniquement, documentés |
| **Aucune donnée réelle exposée** | Le produit n'a ni utilisateurs ni infrastructure réelle ; le connecteur est simulé et marqué comme tel |
| **Risque présent le plus important** | 8 vulnérabilités Python uniques (16 occurrences : starlette 0.41.3 et pytest 8.3.4 dev-only) ; la surface actuelle de l'API est limitée, mais les dépendances restent présentes et une montée FastAPI est à planifier |
| **Conteneurs** | Les 4 images tournent en non-root (CI vérifiée) ; les ports hôte sont désormais liés à `127.0.0.1` et contrôlés automatiquement |
| **Authentification / isolation** | **Non implémentées** (PHASE 0 = squelettes) — ce ne sont pas des failles présentes, ce sont des contrôles à construire en PHASE 1 (P1-02, P1-04, P1-14) |
| **Écart de documentation** | Les affirmations inexactes de la description initiale de la PR #2 ont été corrigées le 25/11 (voir §9) |

## 1. Authentification / autorisation

**État réel : NON IMPLÉMENTÉ (par conception, PHASE 0).**

- L'API n'expose que 2 endpoints, sans authentification : `GET /health` et
  `GET /api/v1/health`. Les deux sont des sondes de santé publiques (pas de
  données, pas d'accès base).
- Aucun mécanisme OIDC, aucune session, aucun token, aucun RBAC dans le code.
  `SECURITY_ARCHITECTURE.md` définit l'architecture cible (OIDC derrière une
  interface, MFA obligatoire pour les admins, RBAC côté serveur) — à
  implémenter en PHASE 1 (P1-02, P1-04).
- `/docs` (Swagger UI) et `/openapi.json` sont exposés avec les valeurs par
  défaut de FastAPI. En dev c'est acceptable ; **avant toute exposition
  publique, restreindre ou désactiver ces routes** (ou les protéger derrière
  l'authentification).
- **Risque réellement présent : FAIBLE.** Il n'y a rien à protéger aujourd'hui
  (aucune donnée, aucune action sensible). Le risque naîtrait si des endpoints
  métier étaient ajoutés sans authentification — la revue de chaque lot PHASE 1
  doit l'interdire (règle : aucun endpoint métier sans authentification).

## 2. Isolation multi-tenant

**État réel : NON IMPLÉMENTÉ (par conception, PHASE 0).**

- Aucune table, aucun `organization_id`, aucun filtre par organisation : le
  modèle de données n'existe pas encore (migrations Alembic prévues P1-13).
- `DATABASE_DESIGN.md` définit le principe (`organization_id` sur chaque ligne
  métier, RLS à évaluer — ADR-0005). Les tests d'isolation existent en
  squelette (`tests/security/test_tenant_isolation.py`, 2 tests `skip`) et
  doivent être activés en PHASE 1 (P1-14).
- **Risque réellement présent : AUCUN** (pas de données multi-tenant à isoler).
  **Contrôle à construire :** P1-14, avec décision RLS documentée (ADR-0005)
  avant d'écrire le code RLS.

## 3. Gestion des secrets

**État réel : SAIN, avec 2 points de vigilance.**

- ✅ Aucun secret réel dans le dépôt : gitleaks vert sur les runs CI #35–#37
  (« No leaks detected ») ; grep des motifs `password=…`, `api_key=…`,
  `secret=…`, `AKIA…`, `ghp_…`, `sk-…` (hors placeholders) → **aucun résultat**
  (vérifié le 25/11).
- ✅ Les seuls secrets présents sont des placeholders de dev
  (`change_me_dev_only`), documentés dans `docker-compose.yml` (en-tête),
  `.env.example` et `app/core/config.py` (docstring).
- ✅ `.env` est exclu du contexte Docker (`.dockerignore`) ; **aucun vrai
  `.env` dans le dépôt** (vérifié) ; `.env.example` ne contient que des
  placeholders.
- ✅ Les credentials de connecteurs sont prévus comme des **références**
  (`secret_ref` vers Vault), jamais des valeurs en base
  (`DATABASE_DESIGN.md` §2.2).
- ⚠️ **Les mots de passe par défaut sont identiques partout**
  (`change_me_dev_only` pour PostgreSQL ET pour `SECRET_KEY`). En dev local
  c'est acceptable et documenté ; **ne jamais réutiliser ces valeurs hors dev**,
  et les rendre distinctes dès le premier environnement partagé.
- ⚠️ **`.dockerignore` ne couvrait pas `.env.local` / `.env.*.local`** (un
  développeur créant un `.env.local` l'aurait envoyé dans le contexte de
  build, stage builder). Corrigé dans la PR de suivi (`.env.local` et
  `.env.*.local` ajoutés ; `.env.example` reste inclus — le motif `.env`
  ne correspond qu'au fichier nommé exactement `.env`).
- Les secrets de production viendront d'un gestionnaire dédié (interface
  compatible Vault) — décision d'implémentation en PHASE 1 (P1-02/P1-08),
  pas de secret en clair dans Git à aucun moment.

## 4. CORS / CSRF

**État réel : CORS configuré restrictif par défaut ; CSRF non applicable.**

- CORS : `CORSMiddleware` actif dans `app/main.py`, avec
  `allow_origins=settings.cors_origins` = **`["http://localhost:3000"]` par
  défaut** (restrictif, bon), `allow_credentials=True`,
  `allow_methods=["*"]`, `allow_headers=["*"]`.
- ⚠️ `allow_credentials=True` combiné à une liste d'origines élargie en
  production serait dangereux (le navigateur enverrait les cookies vers
  l'origine autorisée). **Règle PHASE 1 :** toute origine ajoutée doit être
  revue ; ne jamais mettre `"*"` dans `cors_origins` avec
  `allow_credentials=True`.
- CSRF : non applicable aujourd'hui — l'API n'utilise pas de cookies
  d'authentification (pas de sessions) et ne sert que des sondes health.
  À réévaluer en PHASE 1 quand les sessions par cookie arriveront (P1-02) :
  `SameSite`, origine vérifiée, token CSRF si formulaire.

## 5. Validation des entrées

**État réel : MINIMALE (cohérent avec le périmètre actuel).**

- Les 2 seuls endpoints ne prennent **aucun paramètre** (pas de query, pas de
  body) — rien à valider, rien à injecter.
- Le socle est en place : Pydantic v2 + `pydantic-settings` (`extra="ignore"`,
  les variables d'environnement inconnues sont ignorées) ; SQLAlchemy 2
  (requêtes paramétrées, pas de SQL construit à la main).
- **À construire en PHASE 1 :** schémas Pydantic stricts sur chaque endpoint
  (types, bornes, rejets explicites), validation des identifiants d'organisation
  côté serveur, protection SSRF sur les URL sortantes des connecteurs
  (listes d'autorisation — `SECURITY_ARCHITECTURE.md` §4).

## 6. Logs

**État réel : LOGGING PAR DÉFAUT, sans secret vérifié.**

- Aucune configuration de logging applicative : les logs sont ceux d'uvicorn
  (démarrage, requêtes). Aucun log applicatif n'écrit de données métier.
- ✅ Aucun mot de passe, token ou secret dans les logs vérifiés (les
  placeholders `change_me_dev_only` apparaissent uniquement dans la
  configuration, jamais dans une sortie de log).
- **À construire en PHASE 1 :** journalisation structurée (JSON), niveaux
  définis, **jamais de secret dans les logs** (règle `SECURITY_ARCHITECTURE.md`
  §6), journal d'audit append-only (`audit_logs`) pour les opérations
  sensibles (P1-12).

## 7. Dépendances

**Versions :** Python 3.12 (Docker `python:3.12-slim`, CI 3.12, local 3.12.3) ;
Node 22 (Docker `node:22-alpine`, CI `setup-node` 22, local 24.22.1).
Migration Node 22 vérifiée dans le run #54 : `npm ci`, lint, typecheck et build Web réussis ; build Docker Web et Compose smoke réussis.

### 7.1 Python — `pip-audit` exécuté le 25/11

**16 entrées, 8 vulnérabilités uniques, dans 2 packages :**

| Package | Version | Vulnérabilité | Correctif |
|---|---|---|---|
| pytest (dev-only) | 8.3.4 | PYSEC-2026-1845 — répertoire `/tmp/pytest-of-{user}`, déni de service local | 9.0.3 (majeure) |
| starlette (transitive de FastAPI) | 0.41.3 | PYSEC-2026-1941 — multipart, gros fichiers | 0.47.2 |
| starlette | 0.41.3 | PYSEC-2026-1942 — en-tête Range, temps quadratique (`FileResponse`) | 0.49.1 |
| starlette | 0.41.3 | PYSEC-2026-161 — en-tête Host non validé (reconstruction d'URL) | 1.0.1 |
| starlette | 0.41.3 | PYSEC-2026-2281 — `StaticFiles` sous Windows | 1.1.0 |
| starlette | 0.41.3 | PYSEC-2026-2280 — dispatch `HTTPEndpoint` par `getattr` | 1.1.0 |
| starlette | 0.41.3 | PYSEC-2026-249 — limites `request.form()` | 1.3.1 |
| starlette | 0.41.3 | PYSEC-2026-248 — chemin de requête non validé (reconstruction d'URL) | 1.3.0 |

**Contexte honnête :** l'API actuelle n'a ni upload de fichier, ni
`FileResponse`, ni `StaticFiles`, ni formulaire, ni `HTTPEndpoint` — la
surface exploitable de ces vulnérabilités **dans ce squelette** est donc
limitée. Mais le code vulnérable est présent dans l'image et servira les
futurs endpoints. **Correction :** fastapi 0.115.6 exige
`starlette<0.42.0,>=0.40.0` (vérifié dans les métadonnées du paquet) — corriger
starlette exige donc une montée de FastAPI. C'est une **décision de mise à
niveau à planifier** (lot dédié, avec re-tests), pas un patch silencieux.
**Aucune mise à niveau n'a été effectuée dans cette PR** (instruction : pas de
mise à niveau majeure non maîtrisée).

**Worker + connecteur :** `pip-audit` → **aucune vulnérabilité connue** dans ces dépendances (worker : celery 5.4.0, packaging 26.4, redis 6.1.0 ; connecteur : httpx 0.28.1, pydantic 2.10.4). Ces versions sont celles des requirements du commit audité.

**Amélioration appliquée :** les dépendances de dev (pytest, pytest-asyncio,
ruff) ont été sorties de `apps/api/requirements.txt` vers un nouveau
`requirements-dev.txt` — l'image Docker n'installe plus pytest/ruff
(surface réduite ; pytest vulnérable hors de l'image).

### 7.2 Node — `npm audit` exécuté en CI (run #54, commit `15ad9b9`, 25/11, Node 22)

- Le proxy de la VM d'audit bloque l'endpoint npm (403), mais l'audit a bien été exécuté en CI sur le lockfile courant : **`npm audit --audit-level=high` → 7 vulnérabilités (1 moderate, 5 high, 1 critical)**. Versions racines du lockfile : Next.js 14.2.35, glob 10.3.10, PostCSS 8.5.33, Zod 3.25.76 et ESLint 8.57.1. Le détail des avis GHSA est conservé ci-dessous.

| Package | Plage affectée | Sévérité | Vulnérabilité (GHSA) |
|---|---|---|---|
| glob | 9.0.0 – 14.0.1 | High | Injection de commande via `-c/--cmd` (`shell:true`) — GHSA-5j98-mcp5-4vw2 ; contournement d'annulation AbortSignal (traversée du système de fichiers après timeout) — GHSA-3g3m-2fjr-6pw4 |
| minimatch | 7.0.0 – 11.0.0 | Moderate | Déni de service via amplification `globparts` — GHSA-g3hv-75wg-m249 |
| next | ≤ 16.3.0-preview.10 | **Critical** | 26 avis, dont RCE non authentifiée (serveurs Windows — GHSA-p293-qw3h-jr36 ; Image Optimization API AVIF/SVG — GHSA-2xp9-vwfh-vxw4, GHSA-2464-fhr4-w9xw), SSRF (WebSocket — GHSA-c4j6-fc7j-m34r ; Server Actions — GHSA-89xv-2m56-2m9x), XSS (CSP nonces — GHSA-ffhc-5mcf-pf4q), DoS Image Optimizer — GHSA-9g9p-9gw9-jx7f |
| postcss | ≤ 8.5.22 | High | XSS via `</style>` non échappé — GHSA-qx2v-qp2m-jg93 ; lecture de fichier arbitraire via `sourceMappingURL` — GHSA-6g55-p6wh-862q ; correctif incomplet — GHSA-fxqj-rqcc-2cmp ; path traversal via `sourceMappingURL` — GHSA-r28c-9q8g-f849 |
| zod | < 4.6.6 | High | Épuisement mémoire sur collections contraintes surdimensionnées — GHSA-mrhx-c7xc-m3w5 |

**Contexte honnête :** le correctif proposé par npm (`npm audit fix --force`)
installe next@16.4.6, eslint-config-next@16.4.6 et zod@4.6.7 — des **breaking
changes** (montée majeure). La surface exploitable actuelle est limitée : le
squelette web n'utilise ni Server Actions, ni Image Optimization, ni
formulaires (aucune donnée réelle, aucune exposition publique). **Aucune mise
à niveau effectuée ici** (instruction : pas de mise à niveau majeure non
maîtrisée) — la montée Next 16 / React 19 / ESLint 10 / Zod 4 / Tailwind 4
est un **lot dédié à planifier** (voir §11), avec re-tests complets.
- `npm outdated` : **aucune dépendance en retard dans les plages déclarées**
  (chaque `Current` == `Wanted`). Les versions `Latest` sont des majeures
  (Next 16, React 19, ESLint 10, Tailwind 4, Zod 4, TypeScript 7) —
  **aucune mise à niveau majeure effectuée** (instruction : pas de mise à
  niveau non maîtrisée). Note : ESLint 8 est en fin de vie (EOL octobre 2024)
  — la montée vers ESLint 9/10 fait partie de la montée Next 16, à planifier.

## 8. Conteneurs

| Contrôle | État avant la PR de suivi | État après |
|---|---|---|
| Utilisateur non-root | ❌ **Toutes les images tournaient en `root`** (défaut `python:3.12-slim` et `node:20-alpine`) | ✅ `USER app` (Python, uid système) / `USER node` (web, uid 1000) — vérifié en CI (`id -u` ≠ 0 pour les 4 images) |
| Images minimales | ✅ `python:3.12-slim`, `node:22-alpine` (pas d'image complète) | ✅ inchangé ; l'image API ne contient plus pytest/ruff (split requirements) |
| Healthchecks | ⚠️ Seulement `db` et `redis` | ✅ Ajoutés : `api` (sonde `/health` via urllib), `web` (wget `/`), `worker` (`celery inspect ping`) ; `connector-sim` exempté (one-shot, exit 0 — documenté) |
| Ports publiés | ❌ `5432`, `6379`, `8000` et `3000` sans IP hôte explicite (écoute potentielle sur toutes les interfaces) | ✅ les 4 ports liés à `127.0.0.1` ; contrôle automatisé de `docker compose config --format json` vert dans le run #54 |
| `--reload` dans l'image API | ⚠️ uvicorn avec `--reload` (outil de dev dans l'image livrée) | ✅ Retiré du CMD (activable en local via `command:` si besoin) |
| Contexte de build | ✅ 572,9 kB après correction `.dockerignore` (PR #2) | ✅ `.env.local` / `.env.*.local` ajoutés ; `.env.example` toujours inclus |
| Secrets dans les images | ✅ Aucun (variables d'environnement uniquement, placeholders dev) | ✅ inchangé |

## 9. Écarts de documentation relevés (PR #2)

La description initiale de la PR #2 (commentaire du 24/11 23h35) contenait des
affirmations qui **ne correspondaient pas au code**. Elles ne constituaient pas
des failles, mais ont été corrigées dans le corps actuel de la PR #2 le
25/11 après vérification des fichiers et des tests :

| Affirmation de la description | Réalité vérifiée |
|---|---|
| « PYTHONPATH : corrigé dans api.Dockerfile, connector.Dockerfile et worker.Dockerfile » | **Faux** : zéro occurrence de `PYTHONPATH` dans les Dockerfiles et le code (grep vérifié). Le diff ne modifie que les chemins COPY. |
| « GET /v1/assets?limit=3 200 (3 actifs), POST /v1/simulate 200 » | **Faux** : l'API n'expose que `GET /health` et `GET /api/v1/health` (vérifié dans `app/main.py` et `app/routers/health.py`). Aucune route `/v1/assets` ni `/v1/simulate` n'existe. Le connecteur-sim est un script CLI one-shot, pas un endpoint HTTP. |
| « pytest : 3 passed (tests/sim/test_sim.py, tests/api/test_health.py) » | **Chemins inexacts** : le seul fichier de test est `apps/api/tests/test_health.py` (3 tests, vérifié). Le nombre « 3 passed » est correct, les chemins ne le sont pas. |
| « .dockerignore : n'excluait pas .git, .venv, node_modules, dist, build, .next, coverage, __pycache__, .env* » | **Inexact** : le `.dockerignore` d'origine excluait déjà `.git`, `.env`, `node_modules`, `.next`, `__pycache__`, `*.pyc`, `.venv` (à la racine). Le vrai problème était l'absence de `**/` pour les dossiers imbriqués — pas l'absence des motifs. |

**Statut :** description de la PR #2 corrigée le 25/11. Les vérifications
historiques rapportées sont : pytest 3 passed (`apps/api/tests/test_health.py`),
ruff OK, tsc 0 erreur, `npm run build` OK, API live `GET /health` 200 et
`GET /api/v1/health` 200, connecteur-sim OK (one-shot, `simulated: true`),
worker healthcheck OK. Le run #54 confirme à nouveau le build Docker, le smoke
Compose et les tests Web sur Node 22.

## 10. Risques réellement présents vs contrôles non encore implémentés

| Risque | Statut | Gravité actuelle |
|---|---|---|
| Vulnérabilités starlette 0.41.3 dans l'image API | **Présent** | Moyenne — surface actuelle limitée, à corriger par montée FastAPI avant d'ajouter des endpoints |
| Vulnérabilité pytest 8.3.4 | **Présent (dev-only)** | Faible — locale uniquement, hors de l'image après le split requirements |
| Images en `root` | **Présent** | Corrigé dans la PR de suivi (non-root vérifié en CI) |
| `--reload` dans l'image API | **Présent** | Corrigé dans la PR de suivi (retiré du CMD) |
| Ports hôte publiés (5432/6379/8000/3000) | **Corrigé** | Liés à `127.0.0.1` ; contrôle CI obligatoire |
| Mots de passe par défaut identiques | **Présent** | Faible en dev local — distincts + Vault dès le premier environnement partagé |
| `/docs` et `/openapi.json` exposés | **Présent** | Faible en dev — à restreindre avant exposition publique |
| CORS `allow_credentials=True` | **Présent** | Faible avec la liste actuelle (`localhost:3000`) — revoir à chaque origine ajoutée |
| Authentification absente | **Non implémenté** | N/A aujourd'hui — P1-02 |
| Isolation multi-tenant absente | **Non implémenté** | N/A aujourd'hui — P1-14 (+ décision RLS, ADR-0005) |
| Journal d'audit absent | **Non implémenté** | N/A aujourd'hui — P1-12 |
| Scan de vulnérabilités en CI | **Non implémenté** | Ajouté en `report-only` dans la PR de suivi (job `security-audit`) |
| Validation des entrées (endpoints métier) | **Non implémenté** | N/A aujourd'hui — PHASE 1, schémas Pydantic stricts |

## 11. Recommandations (ordre)

1. **PR #2 :** description corrigée le 25/11 ; les deux PR restent ouvertes et non fusionnées.
2. **Dépendances Python :** planifier une montée FastAPI/Starlette dans un lot isolé, avec tests de compatibilité avant tout endpoint upload/fichier/formulaire.
3. **Dépendances Node :** Node 22 est migré et testé ; la montée Next 16 / React 19 / ESLint 10 / Zod 4 reste un lot majeur distinct.
4. **Actions GitHub :** le run #54 signale encore que certaines actions (@v4/@v5) ciblent le runtime Node 20, forcé vers Node 24 par le runner ; mettre à jour ces actions dans un lot CI séparé.
5. **P1-01 :** build des 4 images et Compose smoke sont verts en CI ; la validation du workflow local sur un poste Docker normal reste à consigner.
6. **PHASE 1 :** démarrer par migrations Alembic, puis organisations/membres, sessions/OIDC, RBAC, isolation multi-tenant et audit log ; aucun endpoint métier avant authentification et tests d'isolation bloquants.


## 12. Revalidation après revue — 25/11/2026

**Commit audité :** `15ad9b9050c1fe08687e8d7cc47a6a4f756426d4` — **run CI #54**.

- Ports Compose : `127.0.0.1:5432`, `127.0.0.1:6379`, `127.0.0.1:8000`, `127.0.0.1:3000`. Le job `compose-validate` vérifie désormais aussi les adresses hôtes dans le JSON rendu par Compose ; contrôle réussi.
- Node 22 : les trois stages du Dockerfile Web utilisent `node:22-alpine` et les deux configurations `setup-node` utilisent Node 22. Web `npm ci`, lint, typecheck et build réussis ; build de l'image Web réussi.
- Docker : les quatre images ont été construites ; les UID vérifiés sont API 999, Web 1000, Worker 999 et connecteur 999 (aucun root).
- Compose smoke : API, Web et Worker healthy ; endpoints API/Web accessibles ; `connector-sim` termine avec exit code 0 ; les quatre ports publiés apparaissent en `127.0.0.1`.
- API : lint, format et pytest réussis. Gitleaks réussi.
- Dépendances : le job `security-audit` est `success` uniquement parce que les deux étapes d'audit sont `continue-on-error: true`. `pip-audit` retourne 16 entrées / 8 avis uniques (pytest 8.3.4 et starlette 0.41.3). `npm audit --audit-level=high` retourne 7 vulnérabilités (1 moderate, 5 high, 1 critical). Aucun correctif majeur automatique n'a été appliqué.
- Avertissement restant : le runner signale que `actions/checkout@v4` cible encore Node 20 et est forcé vers Node 24 ; cela concerne le runtime des actions GitHub, pas le runtime applicatif Node 22.

Le rapport est volontairement distinct entre les contrôles réussis et les vulnérabilités toujours présentes.