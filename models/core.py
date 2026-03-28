"""Team, Player, Game, PlayerGameStats, TeamGameStats models.

Phase 1: Database Schema & Historical Data Ingestion
"""
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from .base import Base, utcnow


class Team(Base):
    """A WNBA franchise."""
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)
    full_name = Column(String, nullable=False)
    abbreviation = Column(String, unique=True, nullable=False)
    city = Column(String, nullable=False)
    conference = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    games_home = relationship("Game", foreign_keys="Game.home_team_id", back_populates="home_team")
    games_away = relationship("Game", foreign_keys="Game.away_team_id", back_populates="away_team")
    player_game_stats = relationship("PlayerGameStats", back_populates="team")
    team_game_stats = relationship("TeamGameStats", back_populates="team")
    arenas = relationship("Arena", back_populates="team")


class Player(Base):
    """A WNBA player. No team affiliation — that lives at game level."""
    __tablename__ = "players"

    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    position = Column(String)
    height = Column(String)
    weight = Column(String)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    player_game_stats = relationship("PlayerGameStats", back_populates="player")


class Game(Base):
    """A single WNBA game between two teams."""
    __tablename__ = "games"

    id = Column(String, primary_key=True)  # WNBA Stats API game ID (e.g., "1022200034")
    game_date = Column(Date, nullable=False, index=True)
    season = Column(Integer, nullable=False, index=True)
    season_type = Column(String, nullable=False)  # "Regular Season" or "Playoffs"
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    home_score = Column(Integer)
    away_score = Column(Integer)
    game_status = Column(String)  # "Final", "In Progress", "Scheduled"
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="games_home")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="games_away")
    player_game_stats = relationship("PlayerGameStats", back_populates="game")
    team_game_stats = relationship("TeamGameStats", back_populates="game")
    game_officials = relationship("GameOfficial", back_populates="game")


class PlayerGameStats(Base):
    """One player's box score for one game."""
    __tablename__ = "player_game_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "game_id", name="uq_player_game"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    game_id = Column(String, ForeignKey("games.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)  # Team this player was on for this game
    minutes = Column(String)  # "45:30" format
    points = Column(Integer)
    fgm = Column(Integer)  # Field goals made
    fga = Column(Integer)  # Field goals attempted
    fg_pct = Column(Float)  # Field goal percentage
    fg3m = Column(Integer)  # Three-pointers made
    fg3a = Column(Integer)  # Three-pointers attempted
    fg3_pct = Column(Float)  # Three-point percentage
    ftm = Column(Integer)  # Free throws made
    fta = Column(Integer)  # Free throws attempted
    ft_pct = Column(Float)  # Free throw percentage
    oreb = Column(Integer)  # Offensive rebounds
    dreb = Column(Integer)  # Defensive rebounds
    reb = Column(Integer)  # Total rebounds
    ast = Column(Integer)  # Assists
    stl = Column(Integer)  # Steals
    blk = Column(Integer)  # Blocks
    tov = Column(Integer)  # Turnovers
    pf = Column(Integer)  # Personal fouls
    plus_minus = Column(Float)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    player = relationship("Player", back_populates="player_game_stats")
    game = relationship("Game", back_populates="player_game_stats")
    team = relationship("Team", back_populates="player_game_stats")


class TeamGameStats(Base):
    """One team's aggregate box score for one game."""
    __tablename__ = "team_game_stats"
    __table_args__ = (
        UniqueConstraint("team_id", "game_id", name="uq_team_game"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    game_id = Column(String, ForeignKey("games.id"), nullable=False)
    minutes = Column(String)
    points = Column(Integer)
    fgm = Column(Integer)
    fga = Column(Integer)
    fg_pct = Column(Float)
    fg3m = Column(Integer)
    fg3a = Column(Integer)
    fg3_pct = Column(Float)
    ftm = Column(Integer)
    fta = Column(Integer)
    ft_pct = Column(Float)
    oreb = Column(Integer)
    dreb = Column(Integer)
    reb = Column(Integer)
    ast = Column(Integer)
    stl = Column(Integer)
    blk = Column(Integer)
    tov = Column(Integer)
    pf = Column(Integer)
    plus_minus = Column(Float)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    team = relationship("Team", back_populates="team_game_stats")
    game = relationship("Game", back_populates="team_game_stats")
