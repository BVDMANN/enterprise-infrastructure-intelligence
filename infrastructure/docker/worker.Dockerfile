FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/app

WORKDIR /app

# Utilisateur non-root (audit sécurité 25/11) : l'image ne tourne jamais en root.
RUN groupadd -r app && useradd -r -m -g app app

# Contexte de build = racine du dépôt (docker-compose.yml) : chemins relatifs à la racine.
COPY services/worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app services/worker/app ./app

USER app
CMD ["celery", "-A", "app.celery_app.celery_app", "worker", "--loglevel=info"]
