"""
Project-level pytest configuration helpers.
This conftest ensures both `src` and the project root are on sys.path
so tests can import either `hyperfocus_agent.*` (when `src` is on sys.path)
or `src.hyperfocus_agent.*` (if project root is on sys.path) without
requiring test edits.
"""
import os
import sys

HERE = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

# Prepend paths so tests always run with the expected project layout
for p in (SRC_DIR, PROJECT_ROOT):
    if p and p not in sys.path:
        sys.path.insert(0, p)

# Optionally, expose a variable for convenience in tests
PROJECT_ROOT_PATH = PROJECT_ROOT
