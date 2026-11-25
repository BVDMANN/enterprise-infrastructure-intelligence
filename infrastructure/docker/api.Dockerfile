FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System dependency: libpq for psycopg (binary wheel needs none, kept minimal).
# Contexte de build = racine du dépôt (docker-compose.yml) : chemins relatifs à la racine.
COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/api/app ./app
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/alembic ./alembic

EXPOSE 8000

# Development: reload enabled. Production uses a dedicated image/command.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
