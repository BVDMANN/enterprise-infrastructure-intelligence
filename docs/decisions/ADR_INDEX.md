# ADR_INDEX.md — Architecture Decision Records

> Toute évolution de l'architecture suit la procédure de changement
> de la spécification V3 §27 : décrire, justifier, évaluer les impacts
> (technique, sécurité, données, coûts), documenter, faire valider si
> structurant, mettre à jour docs et tests.
>
> Statuts : `Proposé` · `Accepté` · `Refusé` · `Remplacé`.

| ADR | Titre | Statut | Date |
|---|---|---|---|
| [ADR-0001](ADR-0001.md) | Monolithe modulaire + Control Plane / Data Plane | Accepté | 2026-11-24 |
| [ADR-0002](ADR-0002.md) | Stack technique fixée (Next.js + FastAPI) | Accepté | 2026-11-24 |
| [ADR-0003](ADR-0003.md) | PostgreSQL + Redis + Celery | Accepté | 2026-11-24 |
| [ADR-0004](ADR-0004.md) | Métriques : VictoriaMetrics (+ Prometheus) | Accepté | 2026-11-24 |
| [ADR-0005](ADR-0005.md) | Authentification OIDC + RBAC ; RLS à évaluer | Accepté | 2026-11-24 |

## Règles

- Un ADR est créé **avant** toute décision structurante (stack, modèle
  de données partagé, contrat d'API, sécurité, déploiement).
- Ne jamais modifier silencieusement l'architecture de référence.
- Un ADR remplacé reste dans l'index avec son statut et un lien vers
  son successeur.
