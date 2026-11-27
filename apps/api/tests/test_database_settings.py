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
