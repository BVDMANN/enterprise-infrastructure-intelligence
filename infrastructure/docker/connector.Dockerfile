FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/app \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

# Utilisateur non-root (audit sécurité 25/11) : l'image ne tourne jamais en root.
RUN groupadd -r app && useradd -r -m -g app app

# Contexte de build = racine du dépôt (docker-compose.yml) : chemins relatifs à la racine.
COPY services/connector/requirements.txt ./requirements.txt

# Installer les dépendances dans un virtualenv isolé, réutilisé au runtime.
RUN python -m venv "$VIRTUAL_ENV" \
    && "$VIRTUAL_ENV/bin/python" -m pip install --no-cache-dir -r requirements.txt \
    && python -c "import sys; assert sys.prefix != sys.base_prefix"

COPY --chown=app:app services/connector/app ./app

# Simulation connector only (PHASE 0). Real connectors get their own image.
USER app
CMD ["python", "-m", "app.main"]
