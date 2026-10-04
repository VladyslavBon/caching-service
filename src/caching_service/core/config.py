from functools import lru_cache

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: PostgresDsn | str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/caching_service",
        description="Async SQLAlchemy URL. Tests override it with SQLite.",
    )

    # Input limits protect the service (and the downstream transformer) from abusive payloads.
    max_list_length: int = Field(default=1000, gt=0)
    max_string_length: int = Field(default=1000, gt=0)

    # The transformer simulates an external service, so its latency and fan-out are tunable.
    transformer_delay_seconds: float = Field(default=0.1, ge=0)
    transformer_max_concurrency: int = Field(default=10, gt=0)


@lru_cache
def get_settings() -> Settings:
    # Cached so that env/.env are parsed once; tests can clear it via get_settings.cache_clear().
    return Settings()
