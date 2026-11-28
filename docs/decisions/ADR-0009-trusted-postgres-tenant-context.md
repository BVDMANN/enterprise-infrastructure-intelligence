# ADR-0009 — DB-validated transaction-scoped tenant context

- **Status:** Proposé — prototype CI isolé uniquement ; aucune adoption applicative ou production.
- **Date:** 2026-11-28.
- **Related:** ADR-0005, ADR-0007, PR #47, #49, #64, #68, #71, #72.

## Context

Les politiques RLS applicatives existantes s'appuient sur les paramètres PostgreSQL
`app.current_organization_id` et `app.current_user_id`. Un rôle runtime peut
appeler `set_config(..., true)` avec des valeurs arbitraires. Les politiques
actuelles protègent donc contre les filtres tenant oubliés lorsque le contexte
applicatif est correct, mais elles ne constituent pas une frontière contre une
injection SQL arbitraire exécutée avec le rôle runtime.

Le prototype ADR-0007 démontre les mécaniques RLS, mais utilise lui aussi un GUC
caller-settable. La séparation runtime/migrator et les tests RLS sur les vraies
tables sont nécessaires, mais ne rendent pas le GUC authentique.

## Hypothèse évaluée

Un contexte transactionnel peut être lié à une session serveur déjà valide, sans
faire confiance aux identifiants d'organisation/utilisateur fournis seuls par le
client SQL :

1. Une fonction PostgreSQL étroitement accordée, `SECURITY DEFINER`, reçoit le
   token de session opaque déjà présenté par l'utilisateur.
2. Elle calcule son digest et vérifie la session, son expiration/révocation,
   l'utilisateur actif/non supprimé, le membership actif et l'organisation non
   supprimée.
3. Elle lit une clé HMAC privée, inaccessible au rôle runtime, et calcule une
   empreinte de contexte à partir de l'organisation, de l'utilisateur, du PID
   PostgreSQL et de l'identifiant de transaction.
4. Elle acquiert un advisory lock transactionnel avec cette empreinte puis pose
   les deux GUC en `SET LOCAL`.
5. Les helpers appelés par les politiques RLS recalculent l'empreinte et
   vérifient que le lock correspondant est détenu par le backend courant.
   Modifier directement les GUC ne crée pas ce lock et doit donc rester
   fail-closed.

La clé du prototype est générée dans la base éphémère par pgcrypto ; aucune clé,
aucun token réel et aucun secret CI n'est ajouté au dépôt. Le lock transactionnel
est libéré automatiquement au commit ou au rollback. Le PID et l'identifiant de
transaction empêchent de réutiliser un lock d'une autre connexion ou transaction.

## Preuve CI isolée

Le test ajouté à `apps/api/tests/test_postgres_rls_evaluation.py` crée un schéma
et deux rôles temporaires non-superutilisateurs dans la base PostgreSQL jetable.
Il vérifie :

- absence de contexte : lecture vide ;
- falsification directe des deux GUC : lecture vide ;
- session valide : lecture limitée à son organisation ;
- changement des GUC après validation : aucun accès à l'autre organisation ;
- INSERT cross-tenant refusé avec SQLSTATE `42501` ;
- sessions expirée ou révoquée : contexte refusé avec SQLSTATE `28000` ;
- lecture directe des tables de sessions et de clé privée interdite au runtime ;
- réutilisation de connexion après commit : aucun contexte hérité ;
- autre backend : impossible de réutiliser le lock de la première connexion ;
- session valide de l'autre organisation : accès limité à cette autre organisation.

Les fonctions utilisent un `search_path` fixé à `pg_catalog`, des références
qualifiées et des droits EXECUTE ciblés. La fonction de vérification interne
n'est pas exécutable par PUBLIC/runtime.

## Limites et risques à lever avant adoption

Ce résultat reste une preuve de concept, pas une solution production approuvée.

- Il faut adapter la fonction au vrai modèle de sessions et au vrai cycle
  d'authentification ; le test emploie des tables isolées.
- L'API doit transmettre le token de session sans le journaliser, le placer dans
  un GUC ou l'exposer à des requêtes non liées. Un token valide demeure un
  bearer credential pour son identité/organisation.
- Une compromission complète du processus API ou le vol d'un token d'une autre
  organisation n'est pas résolu par ce mécanisme.
- La disponibilité de pgcrypto, la génération/rotation de la clé privée, les
  privilèges des fonctions, la gestion des connexions poolées et les opérations
  des workers/agents doivent être examinés.
- Le contrôle via `pg_locks` peut ajouter un coût par évaluation RLS ; il faut
  mesurer les plans et le débit sous charge.
- Les advisory locks sont une ressource partagée : le comportement en cas de
  saturation, de collision ou de tentative de déni de service doit être testé.
- Le contexte des agents, tâches planifiées, support multi-organisation,
  migrations et opérations plateforme nécessite un contrat distinct.
- Aucune politique RLS métier existante n'est remplacée dans ce lot.

## Critères avant toute adoption

1. Revue indépendante sécurité PostgreSQL/SQLAlchemy du diff et du modèle de
   menace.
2. Intégration explicite à l'authentification réelle et au gestionnaire de
   transactions, avec token absent des logs et GUC.
3. Tests négatifs contre toutes les tables RLS réelles, toutes les mutations,
   les révocations, les changements de membership, le rollback et le pool.
4. Tests de concurrence, de performance et de résistance au déni de service.
5. Procédure de rotation et de restauration de la clé documentée et testée.
6. Revue séparée des contextes agents/workers avant d'élargir l'accès.

**Décision actuelle :** conserver les politiques actuelles fail-closed et leur
limite documentée. Ne pas présenter ce prototype comme une isolation complète,
ne pas activer de nouvelle table et ne pas déployer ce mécanisme avant revue et
intégration explicites.
