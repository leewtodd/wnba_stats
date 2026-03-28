"""@engine_function decorator definition.

Registers analysis functions with metadata for discovery and dynamic invocation.
"""

# Module-level registry that decorated functions add themselves to
_REGISTRY = []


def engine_function(name: str, description: str, parameters: dict):
    """Decorator that registers an analysis function with metadata.

    Usage:
        @engine_function(
            name="compare_teams",
            description="Compare two teams across a stat",
            parameters={
                "team_a": {"type": "str", "description": "Team name or abbreviation"},
                "team_b": {"type": "str", "description": "Team name or abbreviation"},
                "stat": {"type": "str", "description": "Stat column name"},
                "season": {"type": "int", "description": "Season year", "optional": True},
            }
        )
        def compare_teams(team_a, team_b, stat, season=None):
            ...

    Args:
        name: Function identifier for registry
        description: Human-readable description of what the function does
        parameters: Dict mapping parameter name to {"type": ..., "description": ..., "optional": ...}

    Returns:
        Decorator function that attaches metadata and registers the function
    """
    def decorator(func):
        func._engine_meta = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "function": func,
            "module": func.__module__,
        }
        _REGISTRY.append(func._engine_meta)
        return func
    return decorator
