# Intégration frontend — organisations, membres et rôles

Cette branche réutilise le shell navigable de la PR #6 et les endpoints protégés par session et RBAC. Les pages Organisations et Utilisateurs & rôles consomment les données de l'API ; elles n'utilisent pas de fixtures pour les organisations, membres ou rôles.

## Fonctions connectées

- Connexion locale : `POST /api/v1/auth/login`.
- Session courante : `GET /api/v1/auth/me`, utilisée par l'en-tête et la page Utilisateurs & rôles.
- Déconnexion : `POST /api/v1/auth/logout` avec le jeton CSRF de la session.
- Organisations accessibles : `GET /api/v1/organizations`.
- Membres actifs : `GET /api/v1/organizations/{id}/members`. La réponse expose `membership_id` et `role_id` en plus de l'identité, du libellé du rôle et de la date d'adhésion.
- Catalogue des rôles : `GET /api/v1/organizations/{id}/roles`.
- Création d'un membership pour un utilisateur existant : `POST /api/v1/organizations/{id}/memberships`.
- Changement de rôle : `PATCH /api/v1/organizations/{id}/memberships/{membership_id}`.
- Retrait d'un membership : `DELETE /api/v1/organizations/{id}/memberships/{membership_id}`.

La page Utilisateurs & rôles permet maintenant de sélectionner un rôle par son identifiant, d'enregistrer le changement et de retirer un membership. Après une mutation réussie, la liste est rechargée depuis l'API. Les réponses HTTP 401, 403, 404 et 409 sont traitées comme des erreurs métier ; les actions en cours et les succès sont annoncés dans l'interface.

## Sécurité de session et mutations

Le navigateur ne lit jamais le cookie opaque `eii_session`. Le cookie de session reste HttpOnly et les requêtes utilisent `credentials: include`. Le jeton CSRF renvoyé par le login est conservé dans `sessionStorage` pour envoyer l'en-tête `X-CSRF-Token` sur la déconnexion et les mutations de memberships. Il n'est jamais envoyé dans les URLs ou les logs applicatifs.

Les mutations exigent une origine explicitement autorisée, une session active et la permission `members.manage`. L'API vérifie elle-même ces conditions ; masquer ou désactiver un bouton dans le navigateur ne constitue jamais un contrôle d'accès. Le serveur refuse l'auto-suppression et toute rétrogradation/suppression qui retirerait le dernier propriétaire actif (HTTP 409). L'événement d'audit et la mutation métier sont enregistrés dans la même transaction.

La configuration CORS de l'API doit autoriser exactement l'origine du frontend. En développement, le défaut actuel est `http://localhost:3000`. Définir `NEXT_PUBLIC_API_URL` pour une autre adresse API ; cette variable est publique et ne doit contenir aucun secret.

Un compte réel doit être créé par la procédure d'amorçage administrateur documentée dans `apps/api/scripts/bootstrap_admin.py`. Aucun identifiant de démonstration n'est intégré.

## Fonctions encore en démonstration ou livrées séparément

- Infrastructure : ressources et métriques simulées ; aucune télémétrie réelle n'est revendiquée.
- Dashboard : les indicateurs non reliés aux endpoints restent explicitement des données de démonstration ; le healthcheck API est réel.
- Page Événements & audit : son intégration frontend au GET tenant-scoped est suivie séparément dans la PR #34, qui n'est pas incluse dans cette branche enfant de #38. Le backend audit trail et son endpoint sont réels dans la pile parente.

## Hors périmètre

- Création d'organisation, invitation par email et création de comptes depuis l'interface.
- Administration du catalogue des rôles et de leurs permissions.
- OIDC, MFA et provisioning externe.
- Démonstration de l'application effective de PostgreSQL RLS sous un rôle runtime dédié non-superutilisateur.

Les mutations de memberships ne créent pas d'utilisateur et n'envoient aucun email. Elles ne remplacent pas les contrôles RBAC/CSRF côté serveur.
