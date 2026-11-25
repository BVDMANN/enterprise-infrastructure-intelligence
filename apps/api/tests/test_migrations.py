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
    """The session migration must be the only head."""
    assert _script_directory().get_heads() == ["0004_user_password_hash"]


def test_initial_migration_has_no_parent() -> None:
    """The first migration must start a new linear history."""
    revision = _script_directory().get_revision("0001_pg_extensions")
    assert revision is not None
    assert revision.down_revision is None


def test_identity_migration_follows_foundation() -> None:
    """0002_identity must descend directly from 0001_pg_extensions."""
    revision = _script_directory().get_revision("0002_identity")
    assert revision is not None
    assert revision.down_revision == "0001_pg_extensions"


def test_session_migration_follows_identity() -> None:
    """0003_auth_sessions must descend directly from 0002_identity."""
    revision = _script_directory().get_revision("0003_auth_sessions")
    assert revision is not None
    assert revision.down_revision == "0002_identity"


def test_password_hash_migration_follows_sessions() -> None:
    """0004_user_password_hash must descend directly from 0003_auth_sessions."""
    revision = _script_directory().get_revision("0004_user_password_hash")
    assert revision is not None
    assert revision.down_revision == "0003_auth_sessions"


def test_migration_history_is_linear() -> None:
    """The history must be one chain: 0001 -> 0002 -> 0003 (head)."""
    history = list(_script_directory().walk_revisions())
    revisions = [rev.revision for rev in history]
    assert revisions == [
        "0004_user_password_hash",
        "0003_auth_sessions",
        "0002_identity",
        "0001_pg_extensions",
    ]
