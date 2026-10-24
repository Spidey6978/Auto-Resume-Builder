import os
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
from arb.core.paths import get_user_data_dir

logger = logging.getLogger(__name__)

DEFAULT_LOCAL_MODEL = "gemma4:e2b"
DEFAULT_LOCAL_URL = "http://127.0.0.1:11434"
DEFAULT_CLOUD_MODEL = "gemma-4-26b-a4b-it"


@dataclass
class AIConfig:
    mode: str = "auto"                     # "auto" | "local" | "cloud"
    local_provider: str = "ollama"         # "ollama"
    local_model: str = DEFAULT_LOCAL_MODEL # e.g. "gemma4:e2b", "gemma4:e4b", "gemma2:2b"
    local_url: str = DEFAULT_LOCAL_URL     # Ollama API URL
    cloud_provider: str = "gemini"         # "gemini"
    cloud_model: str = DEFAULT_CLOUD_MODEL # e.g. "gemma-4-26b-a4b-it", "gemma-4-31b-it", "gemini-2.5-flash"
    cloud_fallback: bool = True            # In auto mode, fallback to cloud if local is unavailable

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AIConfig":
        valid_fields = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


def get_ai_config_path() -> Path:
    return get_user_data_dir() / "ai_config.json"


def load_ai_config() -> AIConfig:
    """
    Loads AIConfig from user data dir (ai_config.json) with environment variable overrides.
    """
    config_path = get_ai_config_path()
    config = AIConfig()

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                config = AIConfig.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to read AI config from {config_path}: {e}. Using defaults.")

    # Environment variable overrides
    env_mode = os.getenv("ARB_AI_MODE")
    if env_mode in ("auto", "local", "cloud"):
        config.mode = env_mode

    env_model = os.getenv("ARB_LOCAL_MODEL")
    if env_model:
        config.local_model = env_model

    env_url = os.getenv("ARB_LOCAL_URL")
    if env_url:
        config.local_url = env_url

    env_fallback = os.getenv("ARB_CLOUD_FALLBACK")
    if env_fallback is not None:
        config.cloud_fallback = env_fallback.lower() in ("1", "true", "yes")

    env_cloud_model = os.getenv("ARB_CLOUD_MODEL")
    if env_cloud_model:
        config.cloud_model = env_cloud_model

    return config


def save_ai_config(config: AIConfig) -> None:
    """
    Saves AIConfig to user data dir.
    """
    config_path = get_ai_config_path()
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save AI config to {config_path}: {e}")
        raise
