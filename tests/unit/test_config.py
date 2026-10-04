import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy.engine import make_url

from caching_service.core.config import Settings


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # Settings read the real environment and .env; start each test from the defaults.
    for name in ("POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("POSTGRES_DB", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.chdir("/")


def test_database_url_is_assembled_from_parts() -> None:
    settings = Settings(
        postgres_host="db",
        postgres_port=6543,
        postgres_user="app",
        postgres_password=SecretStr("secret"),
        postgres_db="cache",
    )

    url = settings.async_database_url

    assert url.drivername == "postgresql+asyncpg"
    assert (url.host, url.port, url.username, url.password, url.database) == (
        "db",
        6543,
        "app",
        "secret",
        "cache",
    )


def test_parts_are_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_PASSWORD", "from-env")

    url = Settings().async_database_url

    assert url.host == "db"
    assert url.password == "from-env"


def test_special_characters_in_password_survive_a_round_trip() -> None:
    password = "p@ss:w/rd%#?"
    settings = Settings(postgres_password=SecretStr(password))

    rendered = settings.async_database_url.render_as_string(hide_password=False)

    assert make_url(rendered).password == password


def test_full_url_overrides_the_parts() -> None:
    settings = Settings(
        database_url=SecretStr("sqlite+aiosqlite:///test.db"),
        postgres_host="ignored",
    )

    assert settings.async_database_url.drivername == "sqlite+aiosqlite"


def test_password_is_not_exposed_by_repr_or_str_of_the_url() -> None:
    settings = Settings(postgres_password=SecretStr("hunter2"))

    assert "hunter2" not in repr(settings)
    assert "hunter2" not in str(settings.async_database_url)


@pytest.mark.parametrize("field", ["postgres_port", "max_list_length", "log_level"])
def test_invalid_values_are_rejected(field: str) -> None:
    bad = {"postgres_port": 0, "max_list_length": 0, "log_level": "LOUD"}[field]

    with pytest.raises(ValidationError):
        Settings.model_validate({field: bad})
