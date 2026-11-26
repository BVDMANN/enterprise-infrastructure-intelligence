"""Database session and declarative base.

Models live in ``app.models`` (identity tables since P1-A1) and are
registered on ``Base.metadata``; Alembic migrations are the source of
truth for the schema — never ``Base.metadata.create_all()`` outside
tests.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Yield a database session (FastAPI dependency)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
