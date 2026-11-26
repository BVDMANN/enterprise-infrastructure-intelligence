# Intégration frontend — organisations et membres (P1-A3.2)

Cette branche réutilise le shell de démonstration de la PR #6 et le branche sur les
endpoints en lecture seule de la PR #18. Elle ne modifie ni la PR #6 ni la PR #18.

## Fonctions connectées

- Connexion locale : `POST /api/v1/auth/login`.
- Liste des organisations accessibles : `GET /api/v1/organizations`.
- Membres actifs d'une organisation : `GET /api/v1/organizations/{id}/members`.
- Rôles et permissions d'une organisation : `GET /api/v1/organizations/{id}/roles`.
- Session courante : `GET /api/v1/auth/me`, utilisée par l'en-tête pour vérifier côté serveur que le cookie correspond encore à une session active et afficher le nom de l'utilisateur.
- Déconnexion : `POST /api/v1/auth/logout` avec le jeton CSRF de la session.

Les pages Organisations et Utilisateurs & rôles ne consomment aucune donnée fictive.
Les états 401, 403, 404, chargement et listes vides sont distincts. Les requêtes
navigateur incluent le cookie HttpOnly avec `credentials: include`.

## Sécurité de session

Le navigateur ne lit jamais le cookie opaque `eii_session`. Le jeton CSRF renvoyé
par le login est conservé dans `sessionStorage` pour permettre au bouton de
déconnexion d'envoyer l'en-tête `X-CSRF-Token`. Il ne remplace pas le cookie HttpOnly
et n'est jamais envoyé dans les URLs ou les logs applicatifs.

La configuration CORS de l'API doit autoriser exactement l'origine du frontend.
En développement, le défaut actuel est `http://localhost:3000`. Définir
`NEXT_PUBLIC_API_URL` pour une autre adresse API ; cette variable est publique et
ne doit contenir aucun secret.

Un compte réel doit être créé par la procédure d'amorçage administrateur documentée
dans `apps/api/scripts/bootstrap_admin.py`. Aucun identifiant de démonstration
n'est intégré.

## Fonctions encore en démonstration

- Infrastructure : ressources et métriques simulées.
- Événements & audit : journal fictif ; aucun audit métier append-only n'est livré.
- Dashboard : indicateurs organisation/utilisateur restent marqués comme données de
  démonstration ; seul le healthcheck interroge l'API réelle.

## Hors périmètre

Les endpoints ne proposent encore aucune création d'organisation, invitation,
changement de rôle ou mutation métier. Ces opérations restent désactivées. OIDC/MFA,
RLS PostgreSQL et audit trail append-only restent des lots séparés.
