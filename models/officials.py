"""GameOfficial model.

Phase 1: Database Schema & Historical Data Ingestion
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from .base import Base, utcnow


class GameOfficial(Base):
    """Assignment of a referee to a game."""
    __tablename__ = "game_officials"
    __table_args__ = (
        UniqueConstraint("game_id", "official_id", name="uq_game_official"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String, ForeignKey("games.id"), nullable=False)
    official_id = Column(Integer, nullable=False)  # WNBA Stats API official person ID
    official_name = Column(String, nullable=False)
    jersey_number = Column(String)  # Optional
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    game = relationship("Game", back_populates="game_officials")
