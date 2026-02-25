"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime configuration for the backend service."""

    # Downstream service URLs
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "gpt-oss:20b"
    flux_url: str = "http://flux:8002"
    acestep_url: str = "http://acestep:8001"

    # Storage
    output_dir: str = "/output"
    db_path: str = "/output/studio.db"
    ffmpeg_bin: str = "ffmpeg"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()


settings = get_settings()
