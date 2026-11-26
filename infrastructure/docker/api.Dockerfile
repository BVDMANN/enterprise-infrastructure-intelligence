FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/app \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

# Utilisateur non-root (audit sécurité 25/11) : l'image ne tourne jamais en root.
RUN groupadd -r app && useradd -r -m -g app app

# System dependency: libpq for psycopg (binary wheel needs none, kept minimal).

# Contexte de build = racine du dépôt (docker-compose.yml) : chemins relatifs à la racine.
COPY apps/api/requirements.txt ./requirements.txt

# Isoler les paquets Python dans un virtualenv : pip ne s'exécute pas dans
# l'environnement système et le runtime utilise exactement ce même interpréteur.
RUN python -m venv "$VIRTUAL_ENV" \
    && "$VIRTUAL_ENV/bin/python" -m pip install --no-cache-dir -r requirements.txt \
    && python -c "import sys; assert sys.prefix != sys.base_prefix"

COPY --chown=app:app apps/api/app ./app
COPY --chown=app:app apps/api/alembic.ini ./alembic.ini
COPY --chown=app:app apps/api/alembic ./alembic

EXPOSE 8000

# Pas de --reload dans l'image : le rechargement à chaud est un outil de dev,
# activable en local via `command:` dans docker-compose.yml si besoin.
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
