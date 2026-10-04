import io
from pathlib import Path
from typing import TextIO

import pytest
from pydantic import ValidationError

from caching_service.cli.main import main
from caching_service.cli.settings import CliSettings

REQUEST_JSON = '{"list_1": ["a"], "list_2": ["b"]}'


def parse(*argv: str) -> CliSettings:
    return CliSettings(_cli_parse_args=list(argv))


def test_defaults() -> None:
    settings = parse("-j", REQUEST_JSON)

    assert str(settings.host) == "http://localhost:8000/"
    assert settings.repeat == 1
    assert settings.output == "-"


def test_short_and_long_flags_are_equivalent() -> None:
    short = parse(
        "--host", "http://example.com:9000", "-r", "3", "-o", "out.jsonl", "-j", REQUEST_JSON
    )
    long = parse(
        "--host", "http://example.com:9000",
        "--repeat", "3",
        "--output", "out.jsonl",
        "--json", REQUEST_JSON,
    )  # fmt: skip

    assert short == long


def test_lowercase_h_is_help_not_host(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        parse("-h")

    assert exit_info.value.code == 0
    assert "--host" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    [
        ["-r", "0", "-j", REQUEST_JSON],
        ["-r", "many", "-j", REQUEST_JSON],
        ["--host", "not a url", "-j", REQUEST_JSON],
        ["--host", "ftp://example.com", "-j", REQUEST_JSON],
        [],
        ["-i", "request.json", "-j", REQUEST_JSON],
    ],
    ids=["zero-repeat", "non-numeric-repeat", "bad-url", "non-http-url", "no-input", "two-inputs"],
)
def test_invalid_arguments_are_rejected(argv: list[str]) -> None:
    with pytest.raises((ValidationError, SystemExit)):
        parse(*argv)


def test_environment_variables_do_not_leak_into_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOST", "not a url")
    monkeypatch.setenv("OUTPUT", "somewhere.txt")

    settings = parse("-j", REQUEST_JSON)

    assert settings.output == "-"
    assert str(settings.host) == "http://localhost:8000/"


def test_load_request_from_inline_json() -> None:
    request = parse("-j", REQUEST_JSON).load_request()

    assert (request.list_1, request.list_2) == (["a"], ["b"])


def test_load_request_from_file(tmp_path: Path) -> None:
    path = tmp_path / "request.json"
    path.write_text(REQUEST_JSON, encoding="utf-8")

    assert parse("-i", str(path)).load_request().list_1 == ["a"]


def test_load_request_from_stdin() -> None:
    request = parse("-i", "-").load_request(stdin=io.StringIO(REQUEST_JSON))

    assert request.list_2 == ["b"]


@pytest.mark.parametrize(
    "raw",
    ["not json", '{"list_1": ["a"]}', '{"list_1": ["a"], "list_2": []}'],
    ids=["malformed", "missing-list", "different-length"],
)
def test_load_request_rejects_invalid_body(raw: str) -> None:
    with pytest.raises(ValidationError):
        parse("-j", raw).load_request()


def test_main_reports_usage_errors_with_exit_code_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-r", "0", "-j", REQUEST_JSON]) == 2
    assert "-r/--repeat" in capsys.readouterr().err


def test_main_reports_unreachable_server_with_exit_code_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Port 1 is reserved and not listening, so the connection is refused immediately.
    assert main(["--host", "http://127.0.0.1:1", "-j", REQUEST_JSON]) == 1
    assert "cannot reach the server" in capsys.readouterr().err


def test_main_writes_results_to_the_output_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_run(settings: CliSettings, out: TextIO) -> None:
        out.write('{"iteration": 1}\n')

    monkeypatch.setattr("caching_service.cli.main._run", fake_run)
    target = tmp_path / "results.jsonl"

    assert main(["-j", REQUEST_JSON, "-o", str(target)]) == 0
    assert target.read_text(encoding="utf-8") == '{"iteration": 1}\n'


def test_main_reports_an_unwritable_output_path_with_exit_code_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["-j", REQUEST_JSON, "-o", str(tmp_path / "missing" / "out.jsonl")]) == 1
    assert "cache-cli: ERROR" in capsys.readouterr().err


def test_main_writes_results_to_stdout_by_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fake_run(settings: CliSettings, out: TextIO) -> None:
        out.write('{"iteration": 1}\n')

    monkeypatch.setattr("caching_service.cli.main._run", fake_run)

    assert main(["-j", REQUEST_JSON]) == 0
    assert capsys.readouterr().out == '{"iteration": 1}\n'
