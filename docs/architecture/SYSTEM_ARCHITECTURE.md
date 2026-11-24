# SYSTEM_ARCHITECTURE.md — Enterprise Infrastructure Intelligence

> Version : spécification V3. Statut : PHASE 0 — architecture de
> référence, non encore implémentée au-delà des squelettes.
> Décisions associées : ADR-0001 (Control/Data Plane), ADR-0002 (stack),
> ADR-0003 (PostgreSQL/Redis/Celery), ADR-0004 (métriques).

## 1. Principe fondamental : Control Plane et Data Plane

### 1.1 Control Plane — plateforme centrale (SaaS)

Cœur du produit, hébergé par l'éditeur. Composants :

- Interface web (Next.js).
- API centrale (FastAPI, `/api/v1`).
- Authentification OIDC + MFA, sessions, révocations.
- Organisations, utilisateurs, rôles, permissions (RBAC).
- Inventaire centralisé, gestion des connecteurs.
- Supervision, alertes, incidents, automatisation.
- Intelligence artificielle (via moteur de politiques).
- Optimisation des coûts, rapports.
- Administration SaaS, facturation, audit.

Le Control Plane **n'expose jamais directement** les interfaces
d'administration des clients sur Internet.

### 1.2 Data Plane — environnement du client

Connecteurs / agents déployés chez le client :

- Collecte d'informations, remontée de métriques.
- Synchronisation d'inventaire, transmission d'événements.
- Exécution d'actions **strictement autorisées** uniquement.

Règles :

- Connexions **sortantes** uniquement, chiffrées (TLS récent) et
  authentifiées (**mTLS**, identité unique par connecteur).
- Certificats révocables et renouvelables ; enregistrement et validation
  initiale du connecteur.
- Autorisation limitée à une organisation et à un périmètre précis.
- Files locales temporaires en cas d'interruption réseau ; reprise de
  transmission après reconnexion.
- Protection contre les rejeux, horodatage des messages, validation
  stricte des données reçues, versionnement du protocole.
- **Aucun tunnel d'administration généraliste** vers le réseau client.

## 2. Architecture logicielle : monolithe modulaire

Pas de microservices prématurés. Un monolithe modulaire dont les
domaines métier sont séparés proprement, pour pouvoir extraire des
composants ultérieurement si la charge le justifie (ADR-0001).

```
┌─────────────────────────────────────────────────────────────────┐
│                        CONTROL PLANE                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ Web      │  │ API      │  │ Worker   │  │ Connecteurs      │ │
│  │ Next.js  │◄►│ FastAPI  │◄►│ Celery   │  │ (registre, mTLS) │ │
│  └──────────┘  └────┬─────┘  └────┬─────┘  └──────────────────┘ │
│                     │  SQLAlchemy│  Redis (broker/cache)       │
│              ┌──────┴───────┐    │                              │
│              │ PostgreSQL   │    │  VictoriaMetrics (métriques)│
│              │ (métier)     │    │  OpenTelemetry (traces)     │
│              └──────────────┘    └─────────────────────────────┘
└──────────────────────────────▲──────────────────────────────────┘
                               │ HTTPS + mTLS (sortant, client → SaaS)
┌──────────────────────────────┴──────────────────────────────────┐
│                        DATA PLANE (client)                       │
│  Connecteur Proxmox · Connecteur Debian · Connecteur AWS ·       │
│  Connecteur de simulation (SIMULÉ, démo/tests uniquement)        │
└─────────────────────────────────────────────────────────────────┘
```

Composants initiaux : application web, API backend, worker asynchrone,
connecteur client, base de données, cache + file de tâches, stockage de
métriques, journalisation et observabilité. Interfaces entre composants
explicites et documentées.

## 3. Communication sécurisée

- HTTPS obligatoire, TLS récent.
- mTLS pour les agents ; identité unique par connecteur ; certificats
  révocables/renouvelables.
- Enregistrement et validation initiale du connecteur.
- Autorisation limitée (organisation + périmètre).
- Files locales temporaires, reprise après reconnexion.
- Anti-rejeu, horodatage, validation stricte, versionnement du protocole.
- La communication est documentée (`docs/api/CONNECTOR_SPECIFICATION.md`).

## 4. Flux principaux (résumé)

- **Synchronisation d'inventaire** : connecteur → API (inventaire,
  `connector_sync_runs`) → PostgreSQL → web.
- **Métriques** : connecteur → ingestion → VictoriaMetrics (+ Prometheus
  pour la collecte quand pertinent) → Monitoring Center.
- **Alertes** : règles (seuils, durées) → déduplication/groupement →
  notifications → acquittement → incident éventuel.
- **Automatisation** : workflow (déclencheur, conditions, action) →
  simulation → approbation si risque → exécution contrôlée → vérification
  → journalisation.
- **IA** : question utilisateur → vérification des permissions →
  données autorisées minimisées → analyse → réponse distinguant fait /
  hypothèse / recommandation → toute action passe par le moteur de
  politiques (voir `AI_GOVERNANCE.md`).

## 5. Environnements

Séparation stricte : Development, Testing, Staging, Production.
Aucun credential de production, clé de signature, secret client ou accès
administrateur à une infrastructure réelle ne doit être communiqué aux
agents IA de développement.

## 6. Déploiement et évolution

- Cible : SaaS hybride (Control Plane hébergé par l'éditeur, Data Plane
  chez le client).
- V1 : Docker / Docker Compose ; CI/CD GitHub Actions ; architecture
  compatible Kubernetes à terme, sans l'imposer.
- Évolutions possibles : SaaS dédié, Control Plane privé, déploiement
  chez le client, résidence des données contractuelle — sans réécriture
  complète.

## 7. Observabilité

OpenTelemetry (télémétrie), logs structurés, traces distribuées,
health/readiness/liveness checks, métriques applicatives, alertes
internes, circuit breakers, timeouts, retries bornés avec backoff,
gestion des migrations (Alembic).
