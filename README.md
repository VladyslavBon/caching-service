# Caching Service

A FastAPI microservice that builds payloads from two lists of strings and caches the
expensive part of that work, so the (simulated) external transformer is called as rarely
as possible.

## How it works

`POST /payload` takes two lists of the same length. Each string is run through a
*transformer* (here: upper-casing after an artificial delay, standing in for an external
service). The output is the transformed strings interleaved, starting with `list_1`:

```
list_1 = ["first string", "second string"]    list_2 = ["other string", "another string"]
output = "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING"
```

Two levels of caching keep transformer calls to a minimum:

| Cache | Table | Key | Saves |
|---|---|---|---|
| Per string | `transformations` | hash of the string | a transformer call for any string seen before, in any request |
| Per request | `payloads` | hash of the ordered pair of lists | everything, and the payload id is reused |

For one request the service:

1. Returns the existing payload id if the exact same input was submitted before.
2. Otherwise, collects the **distinct** strings of both lists and looks them up in
   `transformations` with a single query.
3. Calls the transformer only for the strings that are missing, concurrently but with a
   bounded number of calls in flight.
4. Interleaves the results (rebuilt from the *original* lists, so duplicates and order
   are preserved), stores the new transformations and the payload.

Note that swapping the two lists gives a different payload (the interleaving differs) but
costs no transformer calls, as every string is already cached.

## Run it

### Docker Compose

```bash
make up          # or: docker compose up --build
```

Starts Postgres and the service on <http://localhost:8000> (interactive docs at `/docs`).
Migrations are applied automatically on container start.

### Locally

Requires [uv](https://docs.astral.sh/uv/) and Docker (for Postgres).

```bash
make install
make run         # starts Postgres, applies migrations, runs the service with auto-reload
```

Run `make help` for all targets: `test`, `test-unit`, `test-integration`, `coverage`,
`lint`, `format`, `db`, `db-clean`, `migrate`, `up`, `down`. `make db-clean` deletes all cached
data but keeps the schema; the database must be running.

### Configuration

Environment variables (or a `.env` file, see [.env.example](.env.example)):

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_HOST` | `localhost` | Database host |
| `POSTGRES_PORT` | `5432` | Database port |
| `POSTGRES_USER` | `postgres` | Database user |
| `POSTGRES_PASSWORD` | `postgres` | Database password |
| `POSTGRES_DB` | `caching_service` | Database name |
| `DATABASE_URL` | unset | Complete SQLAlchemy URL; overrides the `POSTGRES_*` parts (used by tests for SQLite) |
| `MAX_LIST_LENGTH` | `1000` | Max items per list |
| `MAX_STRING_LENGTH` | `1000` | Max characters per string |
| `TRANSFORMER_DELAY_SECONDS` | `0.1` | Simulated latency of the external service |
| `TRANSFORMER_MAX_CONCURRENCY` | `10` | Max simultaneous transformer calls |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL` |

The limits protect the service and the downstream transformer from abusive requests. The
delay makes the cost of a call, and therefore the benefit of the cache, observable.

## API

### `POST /payload`

```json
{
  "list_1": ["first string", "second string", "third string"],
  "list_2": ["other string", "another string", "last string"]
}
```

| Status | Meaning |
|---|---|
| `201` | Payload created: `{"id": "<uuid>", "message": "Payload created"}` |
| `200` | Identical input was submitted before; same id returned: `"message": "Payload already exists"` |
| `422` | Invalid input (see below) |

Input is rejected when the lists differ in length, are empty, exceed the configured
limits, or contain NUL characters (which PostgreSQL cannot store).

### `GET /payload/{id}`

```json
{
  "output": "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
}
```

`404` for an unknown id, `422` for a malformed one. `GET /health` is used by the Docker
healthcheck.

## CLI

Installed as `cache-cli` (`uv run cache-cli ...`, or `docker compose exec app cache-cli ...`).

```
cache-cli [--host URL] [-r|--repeat N] [-i|--input FILE|-] [-j|--json JSON] [-o|--output FILE|-] [-h|--help]
```

| Option | Default | Description |
|---|---|---|
| `-h`, `--help` | | Print the usage and the list of options, then exit. Nothing is sent to the server |
| `--host` | `http://localhost:8000` | Base URL of the service to talk to. Must be an `http(s)` URL |
| `-r`, `--repeat` | `1` | How many times to submit the payload and read it back (positive integer) |
| `-i`, `--input` | | File with the request JSON, or `-` to read it from stdin |
| `-j`, `--json` | | The request JSON given directly on the command line |
| `-o`, `--output` | `-` | File to write the results to, or `-` for stdout |

The request JSON has the same shape as the body of `POST /payload`:
`{"list_1": [...], "list_2": [...]}`. Exactly one of `--input` and `--json` is required.
Arguments are parsed and validated with Pydantic Settings; the request body is validated
with the same schema the server uses, so bad input fails before any network call.

### Examples

```bash
cache-cli -h                                          # show help
cache-cli -j '{"list_1": ["a"], "list_2": ["b"]}'     # inline JSON, local server
cache-cli -i request.json                             # request from a file
echo '{"list_1": ["a"], "list_2": ["b"]}' | cache-cli -i -    # request from stdin
cache-cli -i request.json -r 5 -o results.jsonl       # 5 iterations, results to a file
cache-cli --host http://example.com:8000 -i request.json     # another server
```

The JSON quoting above is for bash; in PowerShell it is easier to use `-i` with a file.

Each iteration submits the payload and reads it back, printing one JSON line:

```bash
$ cache-cli -r 3 -j '{"list_1": ["a", "b"], "list_2": ["c", "d"]}'
{"iteration": 1, "id": "…", "created": true,  "output": "A, C, B, D", "elapsed_ms": 605.9}
{"iteration": 2, "id": "…", "created": false, "output": "A, C, B, D", "elapsed_ms": 19.9}
{"iteration": 3, "id": "…", "created": false, "output": "A, C, B, D", "elapsed_ms": 19.9}
```

The first iteration pays for the transformer; the following ones show the cache at work.
Exit codes: `0` success, `1` server unreachable / server error / unreadable file,
`2` invalid arguments.

## Project layout

```
src/caching_service/
  api/          routes, request/response schemas, FastAPI dependencies
  core/         settings
  db/           SQLAlchemy models, engine/session factories, dialect helper
  services/     PayloadService (the caching logic), interleaving, hashing
  transformer/  Transformer protocol, simulated implementation, bounded batch calls
  cli/          cache-cli
migrations/     Alembic migrations
tests/          unit/ and integration/
```

## Testing

```bash
make test               # everything
make test-unit
make test-integration
make coverage           # all tests plus a per-file coverage table
make lint               # ruff, ruff format --check, mypy --strict
```

The suite runs on SQLite by default, so no server is needed. To run it on PostgreSQL
(the production database) point `TEST_DATABASE_URL` at a scratch database, for example
the one from `make db`; the tests drop and recreate their tables, so do not use a
database whose data you want to keep:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/caching_service make test
```

Coverage (line and branch) is measured with `make coverage`, which prints a per-file table
with the missing lines. It is configured for greenlets in `pyproject.toml`: SQLAlchemy's async layer runs on them, and
without that setting coverage silently loses the code that runs after a database call.
CI runs it on the PostgreSQL job.

Tests rely on a transformer fake that counts calls, which is how the central requirement
is verified: repeated and overlapping requests make no, or only the necessary, calls.
CI (GitHub Actions) runs lint, the suite on SQLite and on PostgreSQL (plus a check that
migrations match the models), and a Docker build.
