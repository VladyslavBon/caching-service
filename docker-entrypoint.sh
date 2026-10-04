#!/bin/sh
set -e

# Apply migrations before serving so a fresh database works out of the box.
# With several replicas, run this as a separate one-off job instead: concurrent
# migrations would race each other.
alembic upgrade head

exec "$@"
