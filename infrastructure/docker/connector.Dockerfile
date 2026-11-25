FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Contexte de build = racine du dépôt (docker-compose.yml) : chemins relatifs à la racine.
COPY services/connector/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/connector/app ./app

# Simulation connector only (PHASE 0). Real connectors get their own image.
CMD ["python", "-m", "app.main"]
