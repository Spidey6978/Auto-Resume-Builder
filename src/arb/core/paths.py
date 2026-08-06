import os
import sys
from pathlib import Path
from platformdirs import user_data_dir, user_cache_dir

def get_user_data_dir() -> Path:
    """
    Returns the user data directory for ARB.
    This is where the user's specific configurations and canonical profile are stored.
    """
    path = Path(user_data_dir("auto-resume-builder", "arb"))
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_cache_dir() -> Path:
    """
    Returns the cache directory for ARB.
    """
    path = Path(user_cache_dir("auto-resume-builder", "arb"))
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_bundled_data_dir() -> Path:
    """
    Returns the bundled data directory.
    This is where the default templates, static knowledge, and domain configurations
    that ship with the package are stored.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # When packaged by PyInstaller, _MEIPASS is the root of the bundle.
        # We will configure arb.spec to put our package data in _MEIPASS/arb
        return Path(sys._MEIPASS) / "arb"

    # Source / Wheel fallback
    return Path(__file__).parent.parent

def get_bundled_binary_dir() -> Path:
    """
    Returns the directory where bundled binaries (like Tectonic) are located.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "bin"
    
    # In a development environment, assume they are placed in a 'bin' folder at the project root
    return Path(__file__).parent.parent.parent.parent / "bin"
