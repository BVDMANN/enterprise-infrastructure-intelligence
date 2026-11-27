# P1-A3.1 — premières routes HTTP protégées

Cette livraison ajoute des lectures réelles depuis PostgreSQL/SQLAlchemy. Elle ne fournit
aucune donnée de démonstration et n'ajoute aucune opération de mutation.

## Authentification

Les routes exigent une session serveur active. Le cookie opaque `eii_session` est
désormais limité à `Path=/api/v1` afin que le navigateur l'envoie aux routes
d'authentification et aux ressources API. Il reste HttpOnly, Secure hors développement
et SameSite=Lax. Le token brut n'est pas stocké en base ; la session conserve son hash.

Toute future méthode HTTP non sûre (POST/PATCH/PUT/DELETE) doit conserver le contrôle
Origin exact et exiger le CSRF lié à la session ; les routes de ce lot sont GET uniquement.

## Routes livrées

| Méthode | Route | Permission |
|---|---|---|
| GET | `/api/v1/organizations` | `organization.read` par organisation |
| GET | `/api/v1/organizations/{organization_id}` | `organization.read` |
| GET | `/api/v1/organizations/{organization_id}/members` | `members.read` |
| GET | `/api/v1/organizations/{organization_id}/roles` | `roles.read` |

Le tenant est toujours résolu par le membership de l'utilisateur authentifié. Un
identifiant d'organisation fourni dans l'URL ne suffit jamais à obtenir l'accès.

## Réponses d'autorisation

- 401 : cookie absent, session expirée/révoquée ou utilisateur inactif/supprimé.
- 404 : aucune membership active dans l'organisation demandée (ne révèle pas un tenant
  étranger).
- 403 : membership présent, mais permission demandée absente.

Les membres inactifs ou soft-deleted ne sont pas exposés dans la liste des membres.
Les réponses ne contiennent ni hash de mot de passe, ni token de session, ni CSRF token.

## Hors périmètre

Aucun endpoint d'administration RBAC, OIDC/MFA, RLS PostgreSQL ou audit
trail append-only n'est livré par ce lot. Le frontend de démonstration n'est
pas déclaré connecté à ces routes.

## Évolution — P1-A1 completion (27/11/2026)

Les mutations d'organisation, les invitations et les statuts de membre sont
désormais livrés par le lot P1-A1 completion (branche
`phase1/p1-a1-crud-complet`, base PR #51) et documentés dans
[ORGANIZATION_PROVISIONING.md](ORGANIZATION_PROVISIONING.md) et
[ADR-0008](../decisions/ADR-0008-p1-a1-organization-provisioning.md) :

| Méthode | Route | Permission |
|---|---|---|
| POST | `/api/v1/organizations` | Session + CSRF (aucun membership requis) |
| PATCH | `/api/v1/organizations/{organization_id}` | `organization.manage` |
| DELETE | `/api/v1/organizations/{organization_id}` | `organization.manage` |
| POST | `/api/v1/organizations/{organization_id}/invitations` | `members.manage` |
| GET | `/api/v1/organizations/{organization_id}/invitations` | `members.read` |
| DELETE | `/api/v1/organizations/{organization_id}/invitations/{invitation_id}` | `members.manage` |
| PATCH | `/api/v1/organizations/{organization_id}/members/{membership_id}/status` | `members.manage` |
| GET | `/api/v1/invitations/{token}` | Publique (aperçu) |
| POST | `/api/v1/invitations/{token}/accept` | Publique (le jeton autorise) |
