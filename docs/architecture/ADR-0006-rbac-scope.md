# ADR-0006 — RBAC organisation-scoped

- **Statut :** proposé dans PR #17 ; CI run #134 7/7, revue indépendante encore en attente.
- **Date :** 26/11/2026.

## Contexte

Les memberships P1-A1 portaient initialement un rôle texte. P1-A3 doit introduire des permissions nommées et empêcher qu'un rôle propre à une organisation soit affecté à une autre.

## Décision

- Les rôles sont strictement rattachés à une organisation (roles.organization_id NOT NULL). Les rôles globaux de plateforme sont différés jusqu'à la création d'une frontière d'administration plateforme distincte.
- Les memberships référencent role_id avec une clé étrangère composite (organization_id, role_id) vers (roles.organization_id, roles.id). La séparation tenant/role est donc imposée par la base, pas seulement par le service.
- Le catalogue permissions est global et versionné par des noms stables ; role_permissions lie les rôles à ces permissions.
- La migration 0005 convertit les anciens rôles owner/admin/member/viewer en rôles système propres à chaque organisation. Le downgrade refuse de supprimer des rôles personnalisés ou une matrice de permissions modifiée.
- Les contrôles d'autorisation sont exécutés côté serveur à partir de l'utilisateur actif, du membership actif et de l'organisation active. Les routes doivent appeler require_permission avant d'effectuer une mutation.

## Conséquences et limites

- Un rôle ne peut pas être partagé entre deux organisations ; les rôles système sont provisionnés par organisation.
- Le catalogue de permissions peut être partagé, mais une affectation reste liée à un rôle tenant-scoped.
- Ce lot ne livre pas encore les endpoints de gestion des rôles ni l'intégration du guard dans les routes métier. Le service et les tests ne suffisent pas à déclarer l'API RBAC intégrée.
- Les tests inter-tenant et le cycle PostgreSQL de backfill/downgrade/re-upgrade sont validés par le run #134 ; la revue indépendante et l'intégration des guards HTTP restent des portes avant acceptation.
