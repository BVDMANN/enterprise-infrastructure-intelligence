# PRODUCT_REQUIREMENTS.md — Enterprise Infrastructure Intelligence

> Version : spécification V3 (MASTER PROMPT V3, 24/11/2026).
> Statut : **PHASE 0 — exigences figées, produit non construit.**

## 1. Problème

Les équipes informatiques des ETI et grandes entreprises ne connaissent
pas précisément leurs ressources : infrastructures réparties entre
plusieurs environnements, plusieurs interfaces de supervision, incidents
détectés trop tard, ressources sous-utilisées ou surdimensionnées, coûts
cloud opaques, opérations répétitives chronophages, changements sans
traçabilité, absence de vision globale.

## 2. Solution

Une plateforme centralisée (SaaS B2B) qui supervise, administre, optimise
et automatise une partie du système d'information depuis une interface
unique — **sans imposer de remplacer les outils existants** (interopérabilité
progressive).

## 3. Cibles

| Priorité | Cible | Interlocuteurs |
|---|---|---|
| Principale | ETI (plusieurs serveurs, sites, environnements virtualisés, cloud) | DSI, resp. infrastructure, resp. systèmes & réseaux, resp. exploitation, resp. cybersécurité, resp. informatique |
| Secondaire | Grandes entreprises (multi-équipes, multi-entités, gouvernance) | idem + gouvernance |
| Ultérieure | Administrations et gouvernements (souveraineté, hébergement, traçabilité) | idem + exigences réglementaires |

Ne jamais présenter le produit comme certifié ou conforme à un
référentiel sans preuves vérifiables.

## 4. Proposition de valeur — 4 capacités

1. **VISIBILITY** : connaître les ressources, leur état, leurs relations,
   leurs performances.
2. **CONTROL** : centraliser les opérations d'administration autorisées.
3. **INTELLIGENCE** : analyser les événements, détecter les anomalies,
   produire des recommandations.
4. **OPTIMIZATION** : améliorer l'utilisation des ressources, les coûts,
   l'efficacité opérationnelle.

Différenciation : interopérabilité, centralisation, sécurité des
opérations, intelligence opérationnelle, simplification des hybrides.
Ne pas prétendre remplacer immédiatement Datadog, ServiceNow, VMware,
Proxmox, AWS ou les outils spécialisés.

## 5. Cas d'utilisation prioritaires

- U1 — Un responsable informatique ne connaît pas précisément ses ressources.
- U2 — Infrastructures réparties entre plusieurs environnements.
- U3 — Plusieurs interfaces pour surveiller les serveurs.
- U4 — Incidents détectés trop tard.
- U5 — Ressources sous-utilisées ou surdimensionnées.
- U6 — Coûts cloud difficiles à comprendre.
- U7 — Opérations répétitives qui consomment du temps.
- U8 — Changements techniques sans traçabilité.
- U9 — Absence de vision globale de l'état du SI.

Chaque fonctionnalité doit répondre à un cas d'utilisation identifié.
Ne pas développer une fonctionnalité uniquement parce qu'elle semble
impressionnante.

## 6. Modules fonctionnels (15)

| # | Module | Phase |
|---|---|---|
| 1 | Dashboard central | 1 (MVP) |
| 2 | Infrastructure Manager | 1 (MVP) |
| 3 | Proxmox Manager (lecture seule d'abord) | 1 (MVP) |
| 4 | Linux Manager — Debian d'abord (lecture seule) | 1 (MVP) |
| 5 | Cloud Manager — AWS d'abord (lecture seule) | 3 |
| 6 | Monitoring Center | 1 (MVP) |
| 7 | Alerting Center | 2 |
| 8 | Incident Management | 2 |
| 9 | Automation Engine | 2 |
| 10 | AI Operations Assistant | 3 |
| 11 | Cost Intelligence | 3 |
| 12 | Reports & Analytics | 3 |
| 13 | Administration SaaS | 4 |
| 14 | Billing & Subscription | 4 |
| 15 | Commercial Website | 5 |

Détail fonctionnel par module : voir `docs/product/` (à compléter par
module en PHASE 1) et la spécification V3 §7.

## 7. Indicateurs de valeur (à mesurer)

MTTD, MTTR, disponibilité des ressources, incidents détectés / résolus,
opérations automatisées, temps économisé, coût des ressources,
coût des ressources sous-utilisées, économies **estimées** vs économies
**réellement constatées** — toujours distinguer les deux.

## 8. Exigences non fonctionnelles (résumé)

- **Sécurité** : voir `docs/security/SECURITY_ARCHITECTURE.md` et
  `THREAT_MODEL.md` (exigence fondamentale, pas une fonctionnalité tardive).
- **Multi-tenancy** : isolation logique dès le départ, tests d'isolation
  systématiques.
- **Fiabilité** : RPO/RTO documentés, sauvegardes testées par restauration,
  health/readiness/liveness checks.
- **Conformité** : RGPD, NIS2, DORA, AI Act étudiés par cas — ne jamais
  affirmer une conformité sans preuve.
- **UX** : sobre, professionnelle, responsive, accessible (clavier,
  contrastes, libellés) ; chaque bouton a une fonction réelle ; aucune
  donnée fictive présentée comme réelle.
- **Performance** : objectifs mesurables avant de déclarer une charge
  supportée.

## 9. Hors périmètre (V1)

- Remplacement des outils spécialisés existants.
- Déploiement Kubernetes imposé (compatibilité préparée, non imposée).
- Certifications (ISO 27001, SecNumCloud…) sans audit valide.
- Clients, références ou témoignages inventés.
