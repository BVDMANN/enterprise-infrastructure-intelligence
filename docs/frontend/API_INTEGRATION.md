# Intégration frontend — API authentifiée EII

Le frontend réutilise le shell navigable. Les pages indiquées comme intégrées consomment les endpoints protégés du backend ; les données simulées restent signalées et ne remplacent jamais une réponse API en erreur.

## Fonctions intégrées

- Connexion et session : `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `POST /api/v1/auth/logout`.
- Organisations accessibles : `GET /api/v1/organizations`, création, renommage et suppression logique.
- Membres, rôles et invitations : endpoints tenant-scoped de memberships, rôles et invitations ; les mutations utilisent le jeton CSRF de la session.
- Inventaire Infrastructure : `GET/POST /api/v1/organizations/{id}/infrastructure/assets`, `PATCH/DELETE .../{asset_id}`. La page lit et modifie des ressources persistées par organisation.
- Audit : `GET /api/v1/organizations/{id}/audit-events?limit=50`. La page Audit et le panneau « Événements récents » du dashboard lisent les événements persistés.
- Dashboard : healthcheck API, nombre d'organisations accessibles, utilisateurs uniques via les memberships et derniers événements d'audit sont alimentés par les API.

## Sécurité de session et tenant

Les requêtes navigateur utilisent `credentials: include` et `cache: no-store`. Le navigateur ne lit jamais le cookie opaque `eii_session` (HttpOnly). Les mutations envoient `X-CSRF-Token`. Les contrôles de session, membership et RBAC du serveur restent autoritaires ; un identifiant d'organisation fourni par le navigateur n'accorde aucun accès à lui seul.

La configuration CORS doit autoriser exactement l'origine du frontend. En développement, le défaut est `http://localhost:3000`. `NEXT_PUBLIC_API_URL` est une variable publique et ne doit contenir aucun secret. Un compte réel est créé par la procédure d'amorçage administrateur documentée dans `apps/api/scripts/bootstrap_admin.py`.

## Limites fonctionnelles explicites

- **Inventaire ≠ supervision temps réel :** les ressources Infrastructure sont persistées, mais `last_seen_at` n'est pas une preuve d'agent actif. Aucune collecte CPU/RAM, time-series, découverte automatique, synchronisation de connecteur, règle d'alerte ou gestion d'incident n'est livrée par ces écrans.
- **Audit partiel :** les événements affichés proviennent du journal backend. Toutes les opérations métier ne sont pas encore instrumentées ; l'absence d'un événement ne prouve donc pas qu'aucune action n'a eu lieu.
- **Dashboard DEMO :** les ressources/indicateurs de supervision et alertes conservés depuis les fixtures sont explicitement simulés. Seuls les compteurs et événements portant la mention API utilisent des données réelles.
- **Sécurité restante :** OIDC/MFA et RLS PostgreSQL sur les véritables tables métier restent à valider séparément. Le prototype RLS isolé de CI ne prouve pas que les tables métier sont protégées par RLS.
