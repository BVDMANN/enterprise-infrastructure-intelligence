# SECURITY_ARCHITECTURE.md — Enterprise Infrastructure Intelligence

> Version : spécification V3 §10. Statut : PHASE 0 — architecture
> définie, contrôles à implémenter en PHASE 1. La sécurité n'est pas
> une fonctionnalité à ajouter à la fin.

## 1. Principes

1. **Défense en profondeur** : contrôles à chaque couche (réseau,
   application, données, identité).
2. **Moindre privilège** : chaque identité (utilisateur, connecteur,
   service) n'a que les permissions nécessaires.
3. **Zéro confiance implicite** : toute requête est authentifiée et
   autorisée, y compris en interne.
4. **Aucun secret en clair** : ni dans le code, ni dans Git, ni dans
   les logs. Gestionnaire dédié (ex. HashiCorp Vault) via interface.
5. **Auditabilité** : toute opération sensible est journalisée
   (horodatée, attribuable, protégée contre la modification).

## 2. Authentification et sessions

- OIDC (fournisseur de référence isolé derrière une interface
  remplaçable), préparation SAML/SSO.
- MFA (obligatoire pour les rôles administrateurs).
- Sessions sécurisées (cookies `HttpOnly`, `Secure`, `SameSite`) ;
  révocation de sessions ; gestion des appareils/sessions ;
  journal des connexions ; protection contre les tentatives répétées
  (verrouillage progressif + limitation de débit).
- Réinitialisation de sessions lors des changements de permissions.

## 3. Autorisation (RBAC)

- Rôles de référence : Platform Owner, Platform Administrator,
  Organization Owner, Organization Administrator, Infrastructure
  Administrator, Security Administrator, Operator, Auditor, Viewer,
  Billing Administrator.
- Permissions granulaires (`infrastructure.read`, `connector.manage`,
  `alerts.manage`, `incidents.manage`, `automation.create`,
  `automation.execute`, `automation.approve`, `audit.read`,
  `billing.manage`, `organization.manage`, …).
- Vérification **côté serveur** sur chaque route ; jamais de contrôle
  reposant uniquement sur le frontend.
- Isolation multi-tenant : toute requête limitée à l'organisation
  autorisée ; tests d'isolation systématiques ; RLS évaluée (ADR-0005).

## 4. Communications

- HTTPS obligatoire (TLS moderne) ; HSTS.
- **mTLS** pour les connecteurs (identité unique, certificats
  révocables/renouvelables).
- Pas d'exposition directe des interfaces d'administration clientes.
- Protection CSRF quand nécessaire, XSS (échappement + CSP),
  SQL injection (requêtes paramétrées, ORM), SSRF (validation des
  URL sortantes, listes d'autorisation).

## 5. Données

- Chiffrement en transit (TLS) ; chiffrement au repos pour les
  données sensibles et les sauvegardes (chiffrées).
- Credentials de connecteurs : références vers le gestionnaire de
  secrets uniquement, rotation prévue.
- Minimisation des données (RGPD) ; durées de conservation définies ;
  suppression et export des données clients prévus.
- Sauvegardes chiffrées ; restauration testée.

## 6. Audit

Journalisé (append-only, horodaté, attribuable, protégé) :
connexions et échecs, changements de permissions, création/révocation
de connecteurs, modifications de configuration, approbations, actions
exécutées, accès support, changements de facturation, actions
administratives. **Jamais de mot de passe, token ou secret en clair
dans les logs.**

## 7. Environnements et chaîne de déploiement

- Séparation stricte dev / test / staging / production.
- Aucun credential de production communiqué aux agents IA de dev.
- CI obligatoire : lint, typecheck, tests, scan secrets, scan
  dépendances, analyse statique, scan des images Docker.
- Images Docker scannées ; politique de dépendances (mises à jour,
  vulnérabilités connues).
- Protection de `main`, revue obligatoire des PR.

## 8. Accès support (éditeur)

Les administrateurs internes ne disposent **pas** d'un accès illimité
aux données techniques des clients. Tout accès support est limité,
justifié, autorisé et audité.

## 9. Conformité (renvoi)

Voir `docs/compliance/` (matrice à rédiger en PHASE 1) : RGPD, NIS2,
DORA, AI Act selon les clients. **Ne jamais prétendre une certification
(ISO 27001, SecNumCloud…) sans audit et certification valides.**
