#!/bin/bash
# Development mode entrypoint
# Installs the package in editable mode after source is mounted

set -e

poetry install --no-interaction --no-ansi

echo "Ready! Working directory: $(pwd)"

cd /workspace/test_area

# Execute the command passed to the container
exec "$@"