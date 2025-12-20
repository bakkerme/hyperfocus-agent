# Hyperfocus Agent

Hyperfocus is a LangChain-based agent focused on processing and extracting data from web pages.
It provides a CLI, a web-aware toolset, and a routing layer that selects local, remote, or
multimodal models based on context. This system is optimised towards open-weight LLMs and is predominately tested with GPT-OSS-120b.

## Highlights

- Web loading with stored HTML, DOM skeleton, and markdown outline for repeatable extraction.
- Image reasoning capabilities
- Data tools for CSV loading, querying, and reuse across tasks.
- Middleware for context trimming, image handling, and tool availability gating.
- Can switch to a remote model for high context length reasoning

## Quick start

Prerequisites:
- Python 3.12+
- Poetry

Install dependencies:

```bash
poetry install
```

Set required environment variables:

```bash
export LOCAL_OPENAI_BASE_URL=...
export LOCAL_OPENAI_API_KEY=...
export LOCAL_OPENAI_MODEL=...

export REMOTE_OPENAI_BASE_URL=...
export REMOTE_OPENAI_API_KEY=...
export REMOTE_OPENAI_MODEL=...
```

Optional multimodal variables (for vision or OCR):

```bash
export MULTIMODAL_OPENAI_BASE_URL=...
export MULTIMODAL_OPENAI_API_KEY=...
export MULTIMODAL_OPENAI_MODEL=...
```

Run the agent:

```bash
poetry run hyperfocus "extract prices from https://example.com"
```

## CLI usage

- `poetry run hyperfocus "message"`
  - Default entrypoint, backed by `src/hyperfocus_agent/main.py`.
- `poetry run hyperfocus-lc "message"`
  - Alternate wrapper used in `QUICK_START.md`.
- `poetry run ocr /path/to/image.jpg`
  - Standalone OCR utility (`src/hyperfocus_agent/ocr.py`).

## How web extraction works

1. The agent loads a page with `web_load_web_page` and stores:
   - Raw HTML to disk (`page_<hash>.html`)
   - A DOM skeleton
   - A markdown outline
2. You can then extract data via XPath or grep-like lookup tools.
3. Results can be stored in agent state for follow-on tasks.

## Architecture overview

Entry: `src/hyperfocus_agent/main.py`

Key components:
- Prompts: `src/hyperfocus_agent/prompts.py`
- State schema: `src/hyperfocus_agent/langchain_state.py`
- Toolset: `src/hyperfocus_agent/langchain_tools/`
- Model config and routing: `src/hyperfocus_agent/model_config.py`
- Middleware:
  - `context_middleware.py` (keeps only the latest script per path)
  - `image_middleware.py` (routes to multimodal when images are present)
  - `tool_middleware.py` (gates web tools until a page is loaded)
  - `logging_middleware.py` (logs tool calls and args)

## Testing

Run the test suite:

```bash
poetry run pytest
```

## Notes

- The router uses `LLM_ROUTER_THRESHOLD` (default 10000 chars) to decide when to
  switch to remote models as context grows.
- Observability can be enabled with `PHOENIX_COLLECTOR_ENDPOINT`
  (defaults to `http://localhost:6006`).

## Docs

- `QUICK_START.md`
- `AGENTS.md`
