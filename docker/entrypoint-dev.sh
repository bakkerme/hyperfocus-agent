#!/bin/bash
# Development mode entrypoint
# Installs the package in editable mode after source is mounted

set -e

export PATH="$HOME/.local/bin:$PATH"

# Install the package for the current user without touching system or mounted files owned by root
# pip install --user --no-deps --editable /app
poetry install  --no-interaction --no-ansi

echo "Ready! Working directory: $(pwd)"

cd /workspace/test_area

# Execute the command passed to the container
exec "$@"
