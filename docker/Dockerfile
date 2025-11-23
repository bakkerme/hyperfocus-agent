# Dockerfile for Hyperfocus Agent Testing Environment
FROM python:3.12-slim

# Install Poetry
RUN pip install poetry==1.7.1

RUN apt update && apt install -y --no-install-recommends ripgrep wget curl

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml poetry.lock ./
COPY README.md ./
COPY . /app/

# Configure Poetry to not create virtual env (we're already in a container)
RUN poetry config virtualenvs.create false

# Install dependencies and the package itself
RUN poetry install --no-interaction --no-ansi

# Install the hyperfocus-agent package globally so 'hyperfocus' command is available everywhere
RUN poetry build && pip install dist/*.whl

# Create a safe test workspace directory
RUN mkdir -p /workspace/test_area

# Set the workspace as working directory for testing
WORKDIR /tests/fixtures