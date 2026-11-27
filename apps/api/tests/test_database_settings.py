from app.core.config import Settings


def test_alembic_database_url_falls_back_to_runtime_url() -> None:
    runtime_url = "postgresql+psycopg://runtime:dev-only@localhost:5432/eii"
    settings = Settings(_env_file=None, database_url=runtime_url)

    assert settings.alembic_database_url == runtime_url


def test_alembic_database_url_prefers_dedicated_migration_url() -> None:
    runtime_url = "postgresql+psycopg://runtime:dev-only@localhost:5432/eii"
    migration_url = "postgresql+psycopg://migrator:dev-only@localhost:5432/eii"
    settings = Settings(
        _env_file=None,
        database_url=runtime_url,
        migration_database_url=migration_url,
    )

    assert settings.alembic_database_url == migration_url
    assert settings.database_url == runtime_url

def test_default_database_url_uses_non_privileged_runtime_role(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == (
        "postgresql+psycopg://eii_runtime:change_me_runtime_dev_only@localhost:5432/eii"
    )
    assert settings.alembic_database_url == settings.database_url
