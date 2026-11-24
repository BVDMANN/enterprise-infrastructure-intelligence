# CONNECTOR_SPECIFICATION.md — Enterprise Infrastructure Intelligence

> Version : spécification V3 §11. Statut : PHASE 0 — contrat défini,
> seul le connecteur de simulation est implémenté (squelette).

## 1. Principe

Tous les connecteurs (Proxmox, Debian, AWS, simulation…) implémentent
le **même contrat commun**. Le Control Plane ne connaît que ce contrat :
ajouter un type de connecteur ne modifie pas l'API centrale.

## 2. Contrat commun (capacités obligatoires)

| Capacité | Description |
|---|---|
| Identification | Identifiant unique, version, organisation propriétaire |
| Enregistrement | Enregistrement + validation initiale auprès du Control Plane |
| Authentification | mTLS, identité cryptographique, certificats révocables/renouvelables |
| Vérification de connexion | Test de connexion + vérification des permissions détectées |
| Découverte | Découverte des ressources de l'environnement |
| Synchronisation | Synchronisation d'inventaire (idempotente, avec `sync_run`) |
| Collecte de métriques | Métriques horodatées, cardinalité limitée |
| Transmission d'événements | Événements structurés, horodatés, anti-rejeu |
| Santé du connecteur | Heartbeat, dernière communication, état |
| Gestion de version | Version du connecteur + version du protocole |
| Révocation / déconnexion | Révocation de l'identité, déconnexion propre |

## 3. Données échangées

Chaque message du connecteur contient :

```json
{
  "connector_id": "uuid",
  "protocol_version": "1",
  "organization_id": "uuid",
  "sent_at": "2026-11-24T12:00:00Z",
  "nonce": "…",
  "payload": { "…": "…" },
  "simulated": false
}
```

Règles :

- `simulated` **obligatoire** : `true` uniquement pour le connecteur de
  simulation. Toute donnée simulée doit être identifiable comme telle
  dans l'UI (badge SIMULÉ) et ne jamais être présentée comme réelle.
- Validation stricte côté serveur ; messages invalides rejetés et journalisés.
- Idempotence des synchronisations (déduplication par `external_id`).
- Files locales temporaires en cas d'interruption réseau ; reprise
  après reconnexion ; gestion des doublons et des délais d'attente.

## 4. Cycle de vie d'un connecteur

1. Création de l'identité (Control Plane) → certificat.
2. Configuration chez le client (périmètre, permissions minimales).
3. Vérification de connexion (permissions détectées affichées).
4. Enregistrement.
5. Première synchronisation → inventaire.
6. Collecte continue (métriques, événements).
7. Révocation / déconnexion (fin de vie).

## 5. Connecteur Proxmox (prioritaire, PHASE 1)

- API officielle Proxmox VE, compte ou jeton API **dédié, permissions
  minimales**, lecture seule d'abord.
- Nœuds, clusters, VM, conteneurs, CPU/RAM/stockage, état des tâches,
  informations de sauvegarde, historique de synchronisation.
- Opérations (démarrage, arrêt, redémarrage, migration) : PHASE 2+,
  avec permissions dédiées, simulation préalable, approbation humaine
  selon le risque, exécution contrôlée, journalisation, vérification.

## 6. Connecteur Debian / Linux (prioritaire, PHASE 1)

- Collecte : nom, OS, version, CPU, mémoire, stockage, charge,
  disponibilité, uptime, réseau autorisé, services supervisés,
  métriques, événements sélectionnés.
- Privilégier OpenTelemetry et des collecteurs standards.
- **Aucune commande arbitraire en root.** Toute collecte nécessitant
  des privilèges doit être justifiée, documentée et limitée.
- Extension ultérieure : Windows, autres distributions.

## 7. Connecteur AWS (PHASE 3)

- SDK officiels, rôles IAM et identités temporaires (rôles assumés
  fédérés). **Jamais de clé AWS administrateur globale.**
- Découverte des ressources, instances, réseau, stockage, régions,
  tags, état, métriques, estimation des coûts.
- Lecture seule d'abord. Azure / Google Cloud ensuite, selon la demande.

## 8. Connecteur de simulation

- Même contrat que les connecteurs réels (même code d'interface).
- Données générées localement, marquées `simulated: true` partout.
- Usage : démonstrations, tests, développement sans infrastructure réelle.
- **Interdit** de le présenter comme une infrastructure réelle.
- Implémentation squelette : `services/connector/app/connector.py`
  (classe `SimulationConnector`).

## 9. Sécurité des connecteurs

- mTLS obligatoire ; aucune connexion entrante vers le client.
- Périmètre d'accès minimal ; révocation immédiate possible.
- Aucun tunnel d'administration généraliste.
- Rotation des credentials ; journalisation des enregistrements,
  révocations et échecs de synchronisation.
- Les erreurs réseau, interruptions, délais et reprises sont gérées
  et journalisées (jamais ignorées silencieusement).
