"""Application settings loaded from the environment (.env).

No real secret is stored here: values come from environment variables,
with development-only placeholders as defaults. In staging/production,
secrets come from a dedicated secret manager (e.g. HashiCorp Vault).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_env: str = "development"
    database_url: str = (
        "postgresql+psycopg://eii_runtime:change_me_runtime_dev_only@localhost:5432/eii"
    )
    # Optional, dedicated connection for Alembic. If unset, Alembic falls
    # back to the non-privileged runtime URL and schema changes fail closed.
    migration_database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    secret_key: str = "change_me_dev_only"
    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def alembic_database_url(self) -> str:
        """Return the dedicated migration URL, or the non-privileged runtime URL."""
        return self.migration_database_url or self.database_url


settings = Settings()
