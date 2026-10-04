import sys
from typing import Self, TextIO

from pydantic import AliasChoices, AnyHttpUrl, Field, PositiveInt, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from caching_service.api.schemas import PayloadCreateRequest

STDIO = "-"


class CliSettings(BaseSettings):
    """Submit a payload to the caching service and read it back, optionally repeatedly."""

    model_config = SettingsConfigDict(
        cli_prog_name="cache-cli",
        cli_hide_none_type=True,
        extra="forbid",
    )

    # No short flag: the task assigns `-h` to --host, which clashes with --help.
    host: AnyHttpUrl = Field(
        default=AnyHttpUrl("http://localhost:8000"),
        validation_alias=AliasChoices("host"),
        description="base URL of the caching service",
    )
    repeat: PositiveInt = Field(
        default=1,
        validation_alias=AliasChoices("r", "repeat"),
        description="how many times to submit the payload and read it back",
    )
    input_file: str | None = Field(
        default=None,
        validation_alias=AliasChoices("i", "input"),
        description="file with the request JSON, or - for stdin",
    )
    json_input: str | None = Field(
        default=None,
        validation_alias=AliasChoices("j", "json"),
        description="request JSON given inline",
    )
    output: str = Field(
        default=STDIO,
        validation_alias=AliasChoices("o", "output"),
        description="file to write results to, or - for stdout",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Only the command line counts. Aliases bypass any env prefix, so common
        # variables such as HOST or OUTPUT would otherwise silently leak into the tool.
        return (init_settings,)

    @model_validator(mode="after")
    def _require_exactly_one_input(self) -> Self:
        if (self.input_file is None) == (self.json_input is None):
            raise ValueError("exactly one of -i/--input and -j/--json is required")
        return self

    def load_request(self, stdin: TextIO | None = None) -> PayloadCreateRequest:
        """Read and validate the request body, so bad input fails before any network call."""
        if self.json_input is not None:
            raw = self.json_input
        elif self.input_file == STDIO:
            raw = (stdin or sys.stdin).read()
        else:
            assert self.input_file is not None
            with open(self.input_file, encoding="utf-8") as file:
                raw = file.read()
        return PayloadCreateRequest.model_validate_json(raw)
