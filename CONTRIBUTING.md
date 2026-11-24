# CONTRIBUTING.md — Enterprise Infrastructure Intelligence

## Principes

- La spécification V3 est la source de vérité. Toute décision
  structurante passe par un ADR (`docs/decisions/`).
- Aucune fonctionnalité n'est « terminée » sans tests, documentation
  mise à jour et revue.
- Aucun secret en clair, jamais. Aucune donnée fictive présentée comme
  réelle.

## Branches

- `main` : stable, protégée (revue obligatoire).
- `develop` : intégration.
- `feature/*`, `fix/*`, `security/*`.

## Pull Requests

Chaque PR contient : objectif, description, fichiers concernés, risques,
tests exécutés, captures d'écran si nécessaire, impacts sur la base de
données, documentation modifiée.

## Contrôles CI obligatoires

Lint frontend, typecheck frontend, tests frontend, build frontend,
formatage backend, lint backend, tests backend, vérification des
migrations, scan des secrets, scan des dépendances, analyse statique,
scan des images de conteneurs. Une CI verte ne signifie pas
automatiquement que la fonctionnalité est acceptée.

## Développement local

```bash
cp .env.example .env
docker compose up --build
```

Sans Docker : voir `scripts/check-env.sh` (la VM de référence n'a pas
Docker installé — voir `PROJECT_STATUS.md` §5).

## Règles de code

- Python : typage explicite, `ruff`, docstrings pour les fonctions publiques.
- TypeScript : `strict: true`, Zod pour toute validation d'entrée.
- Code et commentaires en anglais ; documentation produit en français.
- Jamais de stack trace ni de secret exposé au client.
