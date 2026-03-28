"""Allow running scraper with: python -m scraper.runner

Phase 1: Database Schema & Historical Data Ingestion
"""
from .runner import main
import sys

sys.exit(main())
