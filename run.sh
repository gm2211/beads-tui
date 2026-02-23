#!/usr/bin/env bash
# Run beads-tui using the venv's Python but the repo's source code.
DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHONPATH="$DIR" exec "$DIR/.venv/bin/python" -m beads_tui "$@"
