"""Engine module auto-discovery and registry.

Imports all engine modules to trigger @engine_function decorators,
then exports registry functions for external access.
"""

# Import all modules to trigger decorator registration
from . import base  # noqa: F401
from . import utils  # noqa: F401
from . import computed_fields  # noqa: F401
from . import team_matchups  # noqa: F401
from . import player_trends  # noqa: F401
from . import game_context  # noqa: F401
from . import referee_analysis  # noqa: F401
from . import correlation  # noqa: F401

# Export registry functions
from .registry import get_registered_functions, call_function  # noqa: F401

__all__ = ['get_registered_functions', 'call_function']
