"""Registry for @engine_function decorated functions."""
import logging
from engine.base import _REGISTRY

logger = logging.getLogger(__name__)


def get_registered_functions():
    """Get list of all registered engine functions.

    Returns:
        List of dicts, each with keys: name, description, parameters, function, module
    """
    return list(_REGISTRY)


def call_function(name: str, **kwargs):
    """Call a registered engine function by name with arguments.

    Args:
        name: Function name as registered
        **kwargs: Arguments to pass to the function

    Returns:
        Result of the function (typically a pandas DataFrame)
    """
    for func_meta in _REGISTRY:
        if func_meta['name'] == name:
            func = func_meta['function']
            try:
                return func(**kwargs)
            except Exception as e:
                logger.error(f"Error calling function '{name}': {e}")
                import pandas as pd
                return pd.DataFrame()

    logger.error(f"Function '{name}' not found in registry")
    import pandas as pd
    return pd.DataFrame()
