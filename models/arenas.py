"""Arena model.

Phase 1: Database Schema & Historical Data Ingestion
"""
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base


class Arena(Base):
    """Physical venue where a team plays home games."""
    __tablename__ = "arenas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    arena_name = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    season_start = Column(Integer, nullable=False)  # First season at this venue
    season_end = Column(Integer)  # Last season at this venue (null = current)

    # Relationships
    team = relationship("Team", back_populates="arenas")
