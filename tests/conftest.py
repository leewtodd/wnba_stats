"""Shared pytest fixtures for WNBA Stats tests.

IMPORTANT: Before running tests, create the test database:
  createdb wnba_stats_test
"""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

# Use a separate test database to avoid touching real data
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://localhost:5432/wnba_stats_test"
)


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine. Runs once per test session."""
    engine = create_engine(TEST_DATABASE_URL)
    # Create all tables
    Base.metadata.create_all(engine)
    yield engine
    # Drop all tables after tests complete
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(test_engine):
    """Create a fresh database session for each test.
    Rolls back after each test to keep tests isolated.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
