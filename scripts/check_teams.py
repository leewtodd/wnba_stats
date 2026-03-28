"""Quick diagnostic: what team abbreviations are in the database?"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import select
from models import get_engine, get_session_factory, Team

engine = get_engine()
SessionFactory = get_session_factory(engine)
session = SessionFactory()

teams = session.execute(select(Team).order_by(Team.abbreviation)).scalars().all()
print(f"{'ABBR':<6} {'ID':<15} {'FULL NAME':<30} {'CITY':<15}")
print("-" * 70)
for t in teams:
    print(f"{t.abbreviation:<6} {t.id:<15} {t.full_name:<30} {t.city:<15}")
session.close()
