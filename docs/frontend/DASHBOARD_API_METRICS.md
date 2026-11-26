# Dashboard — indicateurs API et données de démonstration

## Données réellement connectées

Le tableau de bord utilise la session HTTP du navigateur (cookie opaque HttpOnly) et les endpoints existants :

- `GET /api/v1/organizations` : nombre d'organisations accessibles à l'utilisateur connecté.
- `GET /api/v1/organizations/{id}/members` : membres actifs de chaque organisation accessible.
- `GET /api/v1/health` : état du Control Plane.

Le compteur d'utilisateurs déduplique les identifiants `user_id` entre les organisations. Il représente les utilisateurs actifs visibles, pas le nombre de memberships.

## Gestion des autorisations et des erreurs

- Pendant le chargement, les compteurs affichent un tiret ; aucune valeur fictive n'est utilisée comme fallback.
- Une réponse 401 indique que la session a expiré et qu'une reconnexion est nécessaire.
- Une réponse 403 sur la lecture des membres masque le total plutôt que d'afficher un compte partiel trompeur.
- Toute autre erreur API affiche « API indisponible » sans substituer des données de démonstration.

Les données sont limitées aux organisations renvoyées par l'API authentifiée. Le navigateur ne choisit pas librement le tenant et ne lit jamais le cookie de session.

## Éléments qui restent simulés

Les cartes Ressources et Alertes, l'aperçu des ressources et les événements récents utilisent toujours `apps/web/lib/demo-data.ts`. Ils sont explicitement étiquetés « DÉMO » ; ils ne représentent aucune infrastructure client connectée et aucun journal d'audit métier réel.

Aucun endpoint de création, d'invitation, de mutation de rôle, d'inventaire réel ou d'audit trail n'est ajouté par ce lot.

## Tests

`npm run test:api` exécute désormais tous les tests Node natifs `lib/*.test.mjs` :

- les tests existants du client HTTP ;
- les tests de déduplication des utilisateurs ;
- les états chargement, zéro résultat, 401, 403 et erreur API ;
- l'absence de fallback vers des compteurs fictifs.

Aucune dépendance n'est ajoutée et le lockfile n'est pas modifié.
