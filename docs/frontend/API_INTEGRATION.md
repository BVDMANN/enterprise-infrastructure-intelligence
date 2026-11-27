# Intégration frontend — API authentifiée

Le frontend réutilise le shell navigable introduit dans la PR #6. Les pages qui
portent le badge « API réelle » consomment les endpoints protégés du backend ;
les données simulées restent explicitement signalées.

## Fonctions connectées

- Connexion locale : `POST /api/v1/auth/login`.
- Session courante : `GET /api/v1/auth/me`.
- Déconnexion : `POST /api/v1/auth/logout` avec le jeton CSRF de la session.
- Organisations accessibles : `GET /api/v1/organizations`.
- Membres actifs : `GET /api/v1/organizations/{id}/members`.
- Rôles et permissions : `GET /api/v1/organizations/{id}/roles`.
- Événements d'audit : `GET /api/v1/organizations/{id}/audit-events?limit=50`.

Les pages Organisations, Utilisateurs & rôles et Événements & audit ne substituent
pas de fixtures aux réponses API. Le dashboard consomme également le journal
d'audit existant pour son panneau « Événements d'audit récents » : il affiche les
trois événements persistés les plus récents parmi les organisations accessibles.
Les états de chargement, listes vides, session absente (401), permission refusée
(403) et organisation non accessible (404) sont présentés séparément. Si une
lecture tenant-scoped échoue pendant l'agrégation du dashboard, le résultat
agrégé est masqué plutôt que présenté comme complet.

Les requêtes navigateur utilisent `credentials: include` pour envoyer le cookie
HttpOnly de session et `cache: no-store`. Le navigateur ne lit jamais le cookie
opaque `eii_session`. Le jeton CSRF renvoyé par le login est conservé dans
`sessionStorage` pour la déconnexion ; il n'est pas envoyé dans les URLs ou les
logs applicatifs.

La configuration CORS de l'API doit autoriser exactement l'origine du frontend.
En développement, le défaut actuel est `http://localhost:3000`. Définir
`NEXT_PUBLIC_API_URL` pour une autre adresse API ; cette variable est publique
et ne doit contenir aucun secret.

Un compte réel doit être créé par la procédure d'amorçage administrateur
documentée dans `apps/api/scripts/bootstrap_admin.py`. Aucun identifiant de
démonstration n'est intégré.

## Couverture de l'audit

La page Audit et le panneau d'audit du dashboard lisent les événements réellement
persistés et autorisés par `audit.read`. Le backend impose une session serveur,
le membership du tenant, un tri du plus récent au plus ancien et une limite
comprise entre 1 et 100.

**La couverture métier reste partielle.** Les workflows actuellement instrumentés
émettent `auth.session.created`, `auth.session.revoked` et
`membership.created`. Une absence d'événement ne prouve donc pas qu'aucune
opération n'a eu lieu : les opérations qui n'appellent pas encore le writer ne
sont pas représentées. Les détails sont ceux persistés par le backend ; le
frontend n'invente ni acteur ni événement.

La page Audit est en lecture seule. Le formulaire de création de membership,
les invitations, les changements de rôle et les suppressions ne sont pas encore
connectés au frontend.

## Fonctions encore en démonstration

- Infrastructure : ressources, métriques, alertes et états de supervision
  simulés ; aucun connecteur client réel n'est présenté comme opérationnel.
- Dashboard : Organisations accessibles, Utilisateurs actifs et Événements
  d'audit récents sont alimentés par les API lorsqu'elles répondent correctement.
  Les ressources et signaux de supervision restent des fixtures DEMO.

## Hors périmètre

OIDC/MFA, RLS PostgreSQL, isolation garantie par un rôle runtime non-superuser,
invitation email, mutation frontend des memberships/rôles, audit exhaustif des
mutations métier et supervision d'infrastructure réelle restent des lots séparés.
