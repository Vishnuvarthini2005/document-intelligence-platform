"""Application configuration loaded from environment variables."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./data/documents.db"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    max_pages: int = 3
    max_file_size_mb: int = 15

    validation_tolerance_pct: float = 0.01
    validation_tolerance_abs: float = 1.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
