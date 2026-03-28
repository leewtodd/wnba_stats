"""Data sources module with auto-discovery."""
from sources.base import DataSource
from sources.injury_reports import InjuryReportsSource


def get_available_sources():
    """Get list of available data sources.

    Returns:
        List of instantiated DataSource objects
    """
    return [
        InjuryReportsSource(),
    ]


__all__ = ['DataSource', 'get_available_sources']
