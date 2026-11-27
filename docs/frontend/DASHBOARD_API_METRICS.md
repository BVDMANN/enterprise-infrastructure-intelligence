# Dashboard — indicateurs API et données de démonstration

## Données réellement connectées

Le tableau de bord utilise la session HTTP du navigateur (cookie opaque HttpOnly) et les endpoints existants :

- `GET /api/v1/health` : état du Control Plane.
- `GET /api/v1/organizations` : organisations accessibles à l'utilisateur connecté.
- `GET /api/v1/organizations/{id}/members` : membres actifs de chaque organisation accessible.
- `GET /api/v1/organizations/{id}/audit-events?limit=50` : événements d'audit persistés de chaque organisation accessible, sous réserve de la permission `audit.read`.

Le compteur d'utilisateurs déduplique les identifiants `user_id` entre les organisations. Il représente les utilisateurs actifs visibles, pas le nombre de memberships.

Le panneau « Événements d'audit récents » agrège les réponses tenant-scoped et affiche les trois événements persistés les plus récents. La lecture est plafonnée à 50 événements par organisation ; il ne s'agit donc pas d'un historique exhaustif. La couverture métier est partielle : seuls les workflows qui écrivent effectivement dans le journal apparaissent.

Cette intégration réutilise l'endpoint d'audit existant ; elle n'ajoute pas de nouvel endpoint backend.

## Gestion des autorisations et des erreurs

- Pendant le chargement, les compteurs affichent un tiret ; aucune valeur fictive n'est utilisée comme fallback.
- Une réponse 401 indique que la session a expiré et qu'une reconnexion est nécessaire.
- Une réponse 403 indique que la permission requise n'est pas disponible.
- Si la lecture d'une organisation échoue, le total et le panneau d'audit agrégés sont masqués plutôt que de présenter un résultat partiel trompeur.
- Toute autre erreur API affiche un état d'indisponibilité sans substituer des données de démonstration.

Les données sont limitées aux organisations renvoyées par l'API authentifiée. Le navigateur ne choisit pas librement le tenant et ne lit jamais le cookie de session.

## Éléments qui restent simulés

Les ressources, l'inventaire, les métriques et les alertes de supervision utilisent toujours les fixtures de démonstration de `apps/web/lib/demo-data.ts`. Ils sont explicitement étiquetés « DÉMO » et ne représentent aucune infrastructure client connectée.

Les événements d'audit affichés sur le dashboard ne proviennent plus de `demo-data.ts` : ils sont lus depuis l'API et restent limités aux événements réellement persistés. Une absence d'événement ne prouve pas qu'aucune opération n'a eu lieu, car toutes les mutations métier ne sont pas encore instrumentées.

## Tests

`npm run test:api` exécute les tests Node natifs `lib/*.test.mjs`, notamment :

- les tests du client HTTP et des états d'autorisation ;
- la déduplication des utilisateurs ;
- les états chargement, zéro résultat, 401, 403 et erreur API ;
- le tri des événements d'audit, la gestion des timestamps invalides et l'absence de mutation des tableaux du cache ;
- l'absence de fallback vers des valeurs de compteurs fictives dans le helper de métriques.

Le panneau d'audit utilise directement les résultats API et affiche des états explicites de chargement, d'erreur ou de liste vide ; il ne dispose pas de jeu d'événements de démonstration.

Aucune dépendance n'est ajoutée et le lockfile n'est pas modifié par cette documentation.
