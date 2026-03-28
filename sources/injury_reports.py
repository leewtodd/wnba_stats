"""Injury reports data source."""
import logging
from typing import List, Dict, Any
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
from sqlalchemy.orm import Session
from models.base import Base, utcnow
from sources.base import DataSource

logger = logging.getLogger(__name__)


class InjuryReport(Base):
    """Injury report data model."""
    __tablename__ = "injury_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    report_date = Column(Date, nullable=False)
    injury_description = Column(String)
    status = Column(String)  # Out, Day-to-Day, Probable, Questionable
    return_date = Column(Date)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class InjuryReportsSource(DataSource):
    """Data source for WNBA injury reports."""

    def __init__(self):
        """Initialize the injury reports source."""
        self.name = "injury_reports"
        self.endpoint = None  # To be validated

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch injury reports from external source.

        Returns:
            Empty list (endpoint not yet validated)
        """
        logger.warning(f"Endpoint not yet validated for {self.name}")
        return []

    def load(self, session: Session) -> None:
        """Load injury reports into database.

        Args:
            session: SQLAlchemy session
        """
        logger.warning(f"Endpoint not yet validated for {self.name}")
        return

    def create_table(self, session: Session) -> None:
        """Create the injury_reports table.

        Args:
            session: SQLAlchemy session
        """
        from models.base import Base, get_engine
        engine = get_engine()
        Base.metadata.create_all(engine, tables=[InjuryReport.__table__])
        logger.info(f"Created table for {self.name}")

    def join_keys(self) -> Dict[str, str]:
        """Specify how this source joins with existing tables.

        Returns:
            Mapping of injury_reports columns to related table columns
        """
        return {
            "player_id": "players.id",
            "team_id": "teams.id",
        }
