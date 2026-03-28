"""Abstract base class for external data sources."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from sqlalchemy.orm import Session


class DataSource(ABC):
    """Abstract base class for external data sources.

    Each data source implements methods for fetching, loading, and integrating
    external data into the WNBA stats platform.
    """

    @abstractmethod
    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch raw data from external source.

        Returns:
            List of dictionaries representing data records
        """
        pass

    @abstractmethod
    def load(self, session: Session) -> None:
        """Load fetched data into database.

        Args:
            session: SQLAlchemy session for database operations
        """
        pass

    @abstractmethod
    def create_table(self, session: Session) -> None:
        """Create database table for this data source.

        Args:
            session: SQLAlchemy session for database operations
        """
        pass

    @abstractmethod
    def join_keys(self) -> Dict[str, str]:
        """Specify how this data source joins with existing tables.

        Returns:
            Dictionary mapping source columns to existing model columns
        """
        pass
