# Hyperfocus Agent – AI Coding Guide

## Architecture Snapshot
- `src/hyperfocus_agent/main.py` is the CLI entry; it enables Phoenix tracing, parses the user message/`--thread-id`, and streams every model token via `StreamingStdOutCallbackHandler` before calling `agent.invoke`.
- `model_config.py` centralizes LLM credential loading: `ModelConfig.from_environment()` validates LOCAL_*, REMOTE_*, and optional MULTIMODAL_* env triads, instantiates `ChatOpenAI` clients with streaming callbacks, and provides `create_non_streaming_local()` for sub-agents that shouldn't pollute stdout.
- `langchain_agent.py` wires the LangChain agent: it calls `ModelConfig.from_environment()`, registers models with middleware via `initialize_models()`, and composes the tool list (all tools including `TASK_TOOLS` are now active).
- `HyperfocusState` in `langchain_state.py` defines required state fields (`messages`, `current_iteration`, `tool_result_metadata`, `use_multimodal`, `stored_data`) used by middleware and any tool returning a `Command`.
- Middleware in `langchain_middleware.py` runs in order: `strip_processed_images` rewrites older messages to stub out images after they are handled, and `dynamic_model_selection` swaps between local, remote, and multimodal models based on message length and detected image blocks (`LLM_ROUTER_THRESHOLD`, default 10000 chars).

## Tooling Patterns
- All LangChain tools live in `src/hyperfocus_agent/langchain_tools` and follow the pattern documented in that folder's README: use `@tool`, take structured params, and either return a string or a `Command` that updates state via `ToolMessage` / artifacts.
- When returning a `Command`, always include the originating `tool_call_id` (available on the injected `ToolRuntime`) so downstream middleware can correlate responses and optionally stash large payloads outside the chat context.
- `file_tools.py`, `directory_tools.py`, and `shell_tools.py` are pure Python wrappers—keep them synchronous and text-only so streaming stdout remains readable.
- `image_tools.load_image` shows how to emit both a confirmation `ToolMessage` and a follow-up `HumanMessage` containing a base64 image to trigger the multimodal route; it also demonstrates MIME detection for remote URLs.
- `task_tools.run_task_on_stored_row_data` demonstrates sub-agent instantiation: it calls `ModelConfig.from_environment()` and `config.create_non_streaming_local()` to spawn an isolated, non-streaming LLM that processes stored CSV rows without polluting stdout or accessing the full conversation history—results are stored as `task_result` entries in both `data_store` and `state.stored_data`.
- `web_tools.readable_web_get` fetches HTML with a desktop UA, runs it through `html2text`, analyzes headings (`mrkdwn_analysis`), and stores the full markdown as a `DataEntry` (keyed by `markdown_<hash>`) in both agent state (`stored_data`) and the global `data_store` helpers. Follow that pipeline when adding extraction helpers, and remember the data-store APIs take only `data_id`—do not pass the LangGraph runtime object.
- `data_store.py` remains the single source of truth for persisted blobs; it has convenience functions for listing, deleting, and size reporting that newer LangChain tools should reuse for consistency.
- Sub-agent tasks (implemented in `task_tools.py`) are synchronous and non-streaming—avoid spawning multiple sub-agents in parallel or adding background event loops inside tools, as Phoenix auto-instrumentation and middleware expect single-threaded execution.

## Critical Workflows
```bash
poetry install                              # once per checkout
export LOCAL_OPENAI_BASE_URL=...
export LOCAL_OPENAI_API_KEY=...
export LOCAL_OPENAI_MODEL=...
export REMOTE_OPENAI_BASE_URL=...
export REMOTE_OPENAI_API_KEY=...
export REMOTE_OPENAI_MODEL=...
poetry run hyperfocus "List files in /tmp"  # add --thread-id to reuse history
```
- Optional: set `MULTIMODAL_OPENAI_*` to enable `image_tools.load_image`, and `PHOENIX_COLLECTOR_ENDPOINT` before running to send traces to Phoenix (default `http://localhost:6006`).
- There are no automated tests yet (`tests/` is empty); sanity-test changes by running representative CLI prompts or by scripting LangChain agent calls in a REPL.

## Running Python
This project uses Poetry for dependency management. Addng dependencies is done via `poetry add <package>`, and running Python REPL is done via `poetry run python -c`.

## Conventions & Pitfalls
- Tool descriptions must stay concise; long outputs should be summarized or stored via `data_store` + metadata so context stays under the router threshold.
- `execute_shell_command` executes with full user privileges and only a 30s timeout—guard against destructive commands and prefer idempotent operations when authoring plans or examples.
- Task tools (implemented in `task_tools.py`) include `run_task_on_stored_row_data` for processing CSV query results via sub-agents; the tool enforces a 200-row limit and stores full results in `data_store` while returning concise summaries to keep main context lean.
- Because Phoenix auto-instrumentation hooks every LangChain call, avoid spawning parallel event loops or threads inside tools; stick to synchronous IO or wrap network calls with clear timeouts.
- Streaming happens directly on stdout; if you add additional prints/logging inside tools or middleware, keep them terse so they do not interleave confusingly with model tokens.

## Go-To Files
- High-level design notes still live in `CLAUDE.md` and Phase docs referenced in `QUICK_START.md`—consult them before reworking routing or tool behaviors.
- `model_config.py` is the single source of truth for LLM credential loading and `ChatOpenAI` instantiation; use `ModelConfig.from_environment()` in any module that needs model access, and call `config.create_non_streaming_local()` for sub-agents.
- `langchain_middleware.py`, `langchain_state.py`, and `langchain_tools/README.md` capture the latest migration conventions; keep new work aligned with those patterns to avoid regressing back to the legacy tool router.
