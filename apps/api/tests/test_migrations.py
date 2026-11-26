"""Structural checks for the Alembic migration graph.

The PostgreSQL upgrade/downgrade itself is exercised by the Compose smoke job.
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def _script_directory() -> ScriptDirectory:
    config_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    config = Config(str(config_path))
    config.set_main_option("script_location", str(config_path.parent / "alembic"))
    return ScriptDirectory.from_config(config)


def test_alembic_has_one_initial_head() -> None:
    """The foundation migration must be the only head."""
    assert _script_directory().get_heads() == ["0001_pg_extensions"]


def test_initial_migration_has_no_parent() -> None:
    """The first migration must start a new linear history."""
    revision = _script_directory().get_revision("0001_pg_extensions")
    assert revision is not None
    assert revision.down_revision is None
