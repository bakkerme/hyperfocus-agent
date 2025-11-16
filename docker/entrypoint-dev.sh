#!/bin/bash
# Development mode entrypoint
# Installs the package in editable mode after source is mounted

set -e

echo "Installing hyperfocus-agent in editable mode..."
poetry install --no-interaction --no-ansi

echo "Ready! Source changes will be reflected immediately."
echo "Working directory: $(pwd)"
echo "Python path: $(python -c 'import sys; print(sys.path)')"

cd /workspace/test_area

# Execute the command passed to the container
exec "$@"