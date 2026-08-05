import os
from pathlib import Path
from platformdirs import user_data_dir

def get_user_data_dir() -> Path:
    """
    Returns the user data directory for ARB.
    This is where the user's specific configurations, canonical profile, 
    and cache are stored.
    """
    path = Path(user_data_dir("auto-resume-builder", "arb"))
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_bundled_data_dir() -> Path:
    """
    Returns the bundled data directory.
    This is where the default templates, static knowledge, and domain configurations
    that ship with the package are stored.
    """
    # __file__ is in src/arb/core/paths.py
    # So the root of the arb package is parent.parent
    return Path(__file__).parent.parent
