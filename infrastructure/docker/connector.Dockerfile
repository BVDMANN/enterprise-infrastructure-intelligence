FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/app

WORKDIR /app

# Utilisateur non-root (audit sécurité 25/11) : l'image ne tourne jamais en root.
RUN groupadd -r app && useradd -r -m -g app app

# Contexte de build = racine du dépôt (docker-compose.yml) : chemins relatifs à la racine.
COPY services/connector/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app services/connector/app ./app

# Simulation connector only (PHASE 0). Real connectors get their own image.
USER app
CMD ["python", "-m", "app.main"]
