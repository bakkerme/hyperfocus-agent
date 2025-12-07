# Hyperfocus Agents

## Purpose
Hyperfocus Agent is an agentic harness that can work with a number of models, specialising in data transformation and lookup. It's written in Pythong and LangChain.

> To run any Python entrypoint or script in this repo, prefix commands with `poetry run` (e.g., `poetry run hyperfocus "hello"`).

## Commands
- `poetry run hyperfocus "message"`: LangChain-powered agent (default entrypoint in `src/hyperfocus_agent/main.py`).
- `poetry run hyperfocus-lc "message"`: Alternate wrapper referenced in `QUICK_START.md` (same core agent).
- `poetry run ocr /path/to/image.jpg`: Standalone OCR CLI (`src/hyperfocus_agent/ocr.py`).

## Environment
- Requires Python >=3.12 with Poetry (see `pyproject.toml`).
- LLM endpoints (OpenAI-compatible) via env vars:
  - Local (required): `LOCAL_OPENAI_BASE_URL`, `LOCAL_OPENAI_API_KEY`, `LOCAL_OPENAI_MODEL`
  - Remote (required): `REMOTE_OPENAI_BASE_URL`, `REMOTE_OPENAI_API_KEY`, `REMOTE_OPENAI_MODEL`
  - Multimodal (optional for vision/OCR): `MULTIMODAL_OPENAI_BASE_URL`, `MULTIMODAL_OPENAI_API_KEY`, `MULTIMODAL_OPENAI_MODEL`
  - Router threshold override: `LLM_ROUTER_THRESHOLD` (default 10000 chars)
  - Observability: `PHOENIX_COLLECTOR_ENDPOINT` (defaults to `http://localhost:6006`)

## Agent Architecture
- Entry: `src/hyperfocus_agent/main.py` builds a LangChain agent with:
  - System prompts from `prompts.py`
  - State schema `langchain_state.py` (messages reducer, optional iteration metadata, stored data, tool list)
  - In-memory checkpointing
  - Toolset from `langchain_tools/*`
  - Middleware chain: context filter (drops old `create_python_script` versions), image stripping, dynamic model routing (multimodal vs local/remote), tool call logging, tool-availability gating (web tools limited until a page is loaded)
- Model config: `model_config.py` loads credentials, instantiates streaming local/remote models, optional multimodal, and provides non-streaming clones for sub-agents. `LLM_ROUTER_THRESHOLD` toggles remote fallback when context grows.

## Tools (LangChain @tool)
- Files/dirs: read/grep/create/append files, create Python script; list/get/change/create directories.
- Shell: `execute_shell_command`.
- Web: `web_load_web_page` (stores HTML + DOM skeleton + markdown outline), `web_get_markdown_view`, `web_extract_with_xpath`, `web_lookup_with_grep`, `get_xpath_list` (sub-agent). Others (CSS/paged search) exist but are not exported.
- CSV: load/describe/query CSV via DuckDB; stores table/query results for later tasks.
- Tasks: `run_task`, `run_task_on_stored_row_data` (sub-agent with optional tools; supports stored data, raw text, images).
- Images: `load_and_ocr_image` (injects OCR result); `load_image` exists but is currently commented out from exports.

## Middleware Highlights
- `context_middleware.py`: keeps only the latest `create_python_script` call/result per path to reduce context bloat.
- `image_middleware.py`: strips processed images after first use; routes to multimodal if images present, otherwise local vs remote based on total message length.
- `tool_middleware.py`: captures canonical tool list and removes web_* tools until a page is loaded.
- `logging_middleware.py`: prints tool name and args before execution.

## Data & State
- `langchain_state.py` supports stored data entries (`data_id`, type, content, metadata) for cross-turn reuse (CSV results, web pages, task outputs, etc.).
- Web loader persists raw HTML to disk (`page_<hash>.html`) for local grep or scripts; outlines include DOM skeleton and heading-based markdown outline.

## Testing Notes
- Pytest configured (`tests/`), covering middleware, HTML outline/skeleton/XPath helpers, and CSV/page utilities. Use `poetry run pytest`.
