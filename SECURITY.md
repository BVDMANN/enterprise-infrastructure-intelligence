# SECURITY.md — Enterprise Infrastructure Intelligence

## Signaler une vulnérabilité

Ne pas ouvrir d'issue publique pour une vulnérabilité. Contacter
l'équipe de sécurité du projet par le canal privé indiqué lors de
l'onboarding (à définir avant toute exposition publique).
Réponse attendue sous 5 jours ouvrés ; correctif coordonné avant
toute divulgation.

## Principes (rappel)

- HTTPS obligatoire, mTLS pour les connecteurs.
- OIDC + MFA, RBAC vérifié côté serveur.
- Aucun secret en clair dans le code, dans Git ou dans les logs.
- Audit append-only des opérations sensibles.
- Multi-tenancy : isolation testée systématiquement.
- Les agents IA de développement ne reçoivent jamais de credentials
  de production, de clés de signature, de secrets clients ou d'accès
  administrateur à des infrastructures réelles.

## Contrôles en place (PHASE 0)

- Scan des secrets en CI (gitleaks).
- Scan des dépendances et des images Docker en CI.
- Analyse statique et lint (ruff, eslint, tsc strict).
- `main` protégée, revue obligatoire.

## Ce qui n'est PAS (encore) en place

Aucune certification (ISO 27001, SecNumCloud…) n'est revendiquée.
Aucun audit de sécurité indépendant n'a été réalisé. La politique
de divulgation coordonnée et le contact sécurité seront définis
avant la première exposition publique (PHASE 4/5).
