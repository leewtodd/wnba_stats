"""SQLAlchemy Base, engine factory, and session management.

Phase 1: Database Schema & Historical Data Ingestion
"""
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def utcnow():
    """Timezone-aware UTC now. Replaces deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc)

# SQLAlchemy declarative base for all models
Base = declarative_base()


def get_engine():
    """Create and return a SQLAlchemy engine.

    Reads DATABASE_URL from environment. Defaults to local Postgres.
    """
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://localhost:5432/wnba_stats"
    )
    return create_engine(database_url, echo=False)


def get_session_factory(engine=None):
    """Create and return a session factory.

    Args:
        engine: SQLAlchemy engine. If None, creates one via get_engine().

    Returns:
        sessionmaker configured for the engine.
    """
    if engine is None:
        engine = get_engine()
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine=None):
    """Create all tables defined by models in the Base metadata.

    Args:
        engine: SQLAlchemy engine. If None, creates one via get_engine().
    """
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(engine)
