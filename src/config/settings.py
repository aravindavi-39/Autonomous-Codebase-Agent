"""Application configuration using Pydantic Settings.

Loads settings from environment variables and .env files.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global application settings.

    Values are loaded from environment variables and .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "Autonomous Codebase Understanding & Refactor Agent"
    app_version: str = "0.1.0"

    # --- LLM ---
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # --- Repository Limits ---
    max_repo_size_mb: int = 500
    max_file_size_kb: int = 500

    # --- Logging ---
    log_level: str = "INFO"

    # --- Paths ---
    project_root: Path = Path(__file__).resolve().parent.parent.parent


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
