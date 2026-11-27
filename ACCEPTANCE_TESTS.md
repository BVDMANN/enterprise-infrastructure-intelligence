# ACCEPTANCE_TESTS.md — Enterprise Infrastructure Intelligence

> Critères d'acceptation généraux (spécification V3 §24).
> Une fonctionnalité ne peut être déclarée ACCEPTED que si les 12
> conditions sont remplies. Statuts : TODO · IN_PROGRESS · BLOCKED ·
> IN_REVIEW · TESTED · ACCEPTED · DEPLOYED.

## Grille d'acceptation (par fonctionnalité)

| # | Critère | Vérification |
|---|---|---|
| 1 | Le besoin est défini | Cas d'utilisation identifié (PRODUCT_REQUIREMENTS §5) |
| 2 | Le parcours utilisateur est documenté | Parcours A–F (§15 de la spécification) |
| 3 | Le backend est fonctionnel | Tests API passés, routes documentées (OpenAPI) |
| 4 | Le frontend est connecté | Appels réels à l'API, pas de données codées en dur |
| 5 | Les permissions sont appliquées côté serveur | Tests d'autorisation (403 sans permission) |
| 6 | Les erreurs sont gérées | États chargement / vide / erreur en UI ; erreurs API stables |
| 7 | Les données sont persistées correctement | Tests d'intégration + migrations revues |
| 8 | Les tests sont exécutés | Unitaires, intégration, e2e (Playwright) verts |
| 9 | La documentation est mise à jour | Docs concernées modifiées dans la même PR |
| 10 | Les risques sont identifiés | Section risques de la PR + THREAT_MODEL si sécurité |
| 11 | La démonstration est reproductible | Étapes de démo documentées, données SIMULÉ marquées |
| 12 | Aucun défaut bloquant connu ne subsiste | Revue + liste des défauts connus vide (bloquants) |

## Distinctions obligatoires

- **Développé** ≠ **testé** ≠ **accepté** ≠ **déployé** ≠ **prêt pour
  la production.** Ne jamais confondre ces états.

## Parcours end-to-end (Playwright, PHASE 1+)

- **A — Première connexion** : connexion → organisation → présentation
  → configuration initiale → invitation → dashboard.
- **B — Ajout d'une infrastructure** : choix du connecteur → prérequis
  → identité → configuration → vérification → permissions → enregistrement
  → première synchronisation → inventaire → erreurs éventuelles.
- **C — Gestion d'une alerte** : détection → qualification →
  notification → acquittement → affectation → incident → résolution →
  clôture → historique.
- **D — Automatisation** : création → ressources → conditions → action
  → simulation → risque → approbation → exécution → vérification →
  journalisation.
- **E — Analyse par IA** : question → permissions → données minimisées
  → analyse → faits/hypothèses → recommandations → moteur de politiques
  → acceptation/refus.
- **F — Administration client** : utilisateurs, rôles, sites,
  connecteurs, notifications, audits, utilisation, abonnement.

## État actuel (fin PHASE 0)

Aucune fonctionnalité métier acceptée. Les squelettes (health checks)
sont couverts par des tests unitaires locaux ; les parcours A–F ne sont
pas implémentables avant la PHASE 1.

## État actuel (P1-A1 completion, 27/11/2026 — local, CI non exécutée)

Le module P1-A1 est complet en local sur `phase1/p1-a1-crud-complet`
(base PR #51) : création/renommage/suppression logique d'organisation,
invitations par lien manuel avec acceptation double mode, statuts de membre
(désactivation/réactivation), réparation de `bootstrap_admin.py`, migration
0007, frontend connecté aux API réelles. 125 tests API locaux (7 skipped) et
36 tests web `test:api` passent ; la CI GitHub n'a pas encore tourné sur ce
lot, donc aucune acceptation n'est revendiquée ici. Voir
`docs/api/ORGANIZATION_PROVISIONING.md` et ADR-0008.
