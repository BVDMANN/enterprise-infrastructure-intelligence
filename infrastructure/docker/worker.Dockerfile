FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Contexte de build = racine du dépôt (docker-compose.yml) : chemins relatifs à la racine.
COPY services/worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/worker/app ./app

CMD ["celery", "-A", "app.celery_app.celery_app", "worker", "--loglevel=info"]
