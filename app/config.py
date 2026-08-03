"""Application configuration loaded from environment variables / .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Typed application settings."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Mesh API (mandatory — all LLM calls go through here) ---------------
    MESH_API_KEY: str = ""
    MESH_BASE_URL: str = "https://api.meshapi.ai/v1"
    MESH_CHAT_MODEL: str = "openai/gpt-4o-mini"
    MESH_EMBED_MODEL: str = "openai/text-embedding-3-small"

    # --- App ---------------------------------------------------------------
    SECRET_KEY: str = "insecure-dev-key-change-me"
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'data' / 'trove.db'}"
    CHROMA_PERSIST_DIR: str = str(BASE_DIR / "chroma_db")

    # --- Bootstrap admin ---------------------------------------------------
    ADMIN_EMAIL: str = "admin@trove.local"
    ADMIN_PASSWORD: str = "admin123"
    SEED_CATALOG: bool = True

    # --- LangSmith (optional) ---------------------------------------------
    LANGSMITH_TRACING: bool = False
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "trove"

    # --- Scheduler --------------------------------------------------------
    DIGEST_HOUR: int = 15
    DIGEST_MINUTE: int = 0

    # --- Recommendation refresh policy ------------------------------------
    RECO_MIN_NEW_EVENTS: int = 5
    RECO_MIN_INTERVAL_MINUTES: int = 10

    # --- Session cookie ---------------------------------------------------
    SESSION_COOKIE_NAME: str = "trove_session"
    SESSION_MAX_AGE_SECONDS: int = 60 * 60 * 24 * 7  # 1 week


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor — call this everywhere instead of instantiating."""
    return Settings()
