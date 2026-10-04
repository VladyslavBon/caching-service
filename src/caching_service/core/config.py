from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # The database is configured by parts, using the variable names of the official
    # Postgres image, so one .env file serves both the service and its container.
    postgres_host: str = "localhost"
    postgres_port: int = Field(default=5432, gt=0, le=65535)
    postgres_user: str = "postgres"
    postgres_password: SecretStr = SecretStr("postgres")
    postgres_db: str = "caching_service"

    # Escape hatch for a complete URL, e.g. SQLite in tests. Takes precedence over the parts.
    database_url: SecretStr | None = None

    # Input limits protect the service (and the downstream transformer) from abusive payloads.
    max_list_length: int = Field(default=1000, gt=0)
    max_string_length: int = Field(default=1000, gt=0)

    # The transformer simulates an external service, so its latency and fan-out are tunable.
    transformer_delay_seconds: float = Field(default=0.1, ge=0)
    transformer_max_concurrency: int = Field(default=10, gt=0)

    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")

    @property
    def async_database_url(self) -> URL:
        if self.database_url is not None:
            return make_url(self.database_url.get_secret_value())
        # Built through URL.create so special characters in the password are escaped
        # properly, which naive string formatting would get wrong.
        return URL.create(
            "postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    # Cached so that env/.env are parsed once; tests can clear it via get_settings.cache_clear().
    return Settings()
