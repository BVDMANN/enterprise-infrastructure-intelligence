# THREAT_MODEL.md — Enterprise Infrastructure Intelligence

> Méthode : **STRIDE**. Version : spécification V3 §10.1.
> Statut : PHASE 0 — modèle initial, à réviser à chaque phase.

## 1. Périmètre

Acteurs : utilisateurs (DSI, opérateurs, auditeurs), administrateurs
de la plateforme, connecteurs/agents chez les clients, fournisseurs
d'identité OIDC, fournisseurs IA externes, attaquants externes,
initiés malveillants ou compromis.

Biens à protéger : données d'infrastructure des clients, credentials
de connecteurs, sessions et identités, données de facturation,
journaux d'audit, disponibilité de la plateforme.

## 2. Analyse STRIDE

### S — Spoofing (usurpation d'identité)

| Menace | Impact | Contrôles |
|---|---|---|
| Vol de compte utilisateur (phishing, credential stuffing) | Accès aux données d'une organisation | OIDC + MFA, détection des tentatives répétées, révocation de sessions, journal des connexions |
| Usurpation d'identité de connecteur | Fausse remontée d'inventaire / métriques | mTLS, identité unique par connecteur, certificats révocables, validation initiale |
| Usurpation du Control Plane par un faux serveur | Vol de credentials de connecteurs | TLS avec validation stricte, certificats épinglés côté agent, enregistrement validé |

### T — Tampering (altération)

| Menace | Impact | Contrôles |
|---|---|---|
| Altération des journaux d'audit | Perte de traçabilité | Audit append-only, horodatage, protection contre la modification |
| Altération des métriques / de l'inventaire en transit | Décisions faussées, alertes manquées | mTLS, horodatage, anti-rejeu, validation stricte des données reçues |
| Modification non autorisée de configuration | Changement d'infrastructure non tracé | RBAC, approbations, audit, versionnement des workflows |

### R — Repudiation (répudiation)

| Menace | Impact | Contrôles |
|---|---|---|
| Action sensible niée par son auteur | Impossibilité d'attribuer un incident | Audit horodaté + identité sur chaque action, approbations enregistrées |
| Exécution d'automatisation non tracée | Opération sans responsable | `workflow_runs` + `automation_actions` journalisés, vérification post-exécution |

### I — Information Disclosure (fuite d'informations)

| Menace | Impact | Contrôles |
|---|---|---|
| Mauvaise isolation entre tenants | Fuite de données d'un client vers un autre | Filtrage par `organization_id` côté serveur, tests d'isolation, RLS évaluée |
| Fuite de secrets (logs, Git, erreurs) | Compromission de connecteurs / comptes | Aucun secret en clair (code, Git, logs), scan secrets en CI, gestionnaire dédié |
| Exposition d'erreurs internes / stack traces | Informations sur l'architecture | Messages d'erreur génériques côté client, détails en logs internes uniquement |
| Transmission de données clients à un fournisseur IA | Fuite / entraînement non consenti | Minimisation, documentation, choix contractuels, désactivation possible |

### D — Denial of Service (déni de service)

| Menace | Impact | Contrôles |
|---|---|---|
| Abus d'API / tempête d'alertes | Indisponibilité, bruit | Limitation de débit, déduplication/groupement d'alertes, circuit breakers, files bornées |
| Ingestion massive de métriques | Saturation du stockage | Cardinalité limitée, rétention configurable, quotas par organisation |
| Boucle d'automatisation | Exécutions en cascade | Limitation du nombre d'exécutions, délais, protection anti-boucle, idempotence |

### E — Elevation of Privilege (élévation de privilèges)

| Menace | Impact | Contrôles |
|---|---|---|
| Élévation via rôle / permission mal configurée | Accès hors périmètre | RBAC granulaire, vérification serveur, tests d'autorisation, revue des rôles |
| IA contournant le moteur de politiques | Action non autorisée exécutée | Toute action IA passe par le moteur déterministe (AI_GOVERNANCE.md) ; l'IA n'a pas de privilège implicite |
| Compromission d'un connecteur | Accès au réseau client | Périmètre minimal, lecture seule d'abord, révocation immédiate, pas de tunnel généraliste |
| Injection (SQL, commandes) / SSRF / RCE | Exécution arbitraire | Validation stricte des entrées, requêtes paramétrées, aucune commande arbitraire en root, validation des URL sortantes |
| Compromission de dépendances / de la chaîne de déploiement | Porte dérobée | Scan dépendances et images, analyse statique, `main` protégée, revue des PR |

## 3. Menaces spécifiques IA

- **Prompt injection** : les instructions provenant des logs, machines,
  documents ou données collectées sont des données non fiables — elles
  ne deviennent jamais des instructions système (voir AI_GOVERNANCE.md).
- **Abus de l'outil IA** : limitation des outils, des requêtes, des
  coûts ; versionnement des modèles et prompts ; traçabilité des
  recommandations.

## 4. Risques résiduels et suivi

- RLS PostgreSQL : efficacité à valider en PHASE 1 (ADR-0005).
- Maturité des contrôles mTLS à l'échelle : à éprouver avec les
  premiers connecteurs réels (PHASE 1).
- Ce modèle est revu à chaque phase et après chaque incident de
  sécurité (voir `docs/security/SECURITY_ARCHITECTURE.md` §10.2).
