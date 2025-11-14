# Hyperfocus Agent – AI Coding Guide

## Architecture Snapshot
- `src/hyperfocus_agent/main.py` is the CLI entry; it enables Phoenix tracing, parses the user message/`--thread-id`, and streams every model token via `StreamingStdOutCallbackHandler` before calling `agent.invoke`.
- `langchain_agent.py` wires the LangChain agent: it validates both LOCAL_* and REMOTE_* env triads, builds `ChatOpenAI` clients (optional multimodal client), registers them with middleware, and composes the tool list (note `TASK_TOOLS` are currently commented out).
- `HyperfocusState` in `langchain_state.py` defines required state fields (`messages`, `current_iteration`, `tool_result_metadata`, `use_multimodal`, `stored_data`) used by middleware and any tool returning a `Command`.
- Middleware in `langchain_middleware.py` runs in order: `strip_processed_images` rewrites older messages to stub out images after they are handled, and `dynamic_model_selection` swaps between local, remote, and multimodal models based on message length and detected image blocks (`LLM_ROUTER_THRESHOLD`, default 10000 chars).

## Tooling Patterns
- All LangChain tools live in `src/hyperfocus_agent/langchain_tools` and follow the pattern documented in that folder's README: use `@tool`, take structured params, and either return a string or a `Command` that updates state via `ToolMessage` / artifacts.
- When returning a `Command`, always include the originating `tool_call_id` (available on the injected `ToolRuntime`) so downstream middleware can correlate responses and optionally stash large payloads outside the chat context.
- `file_tools.py`, `directory_tools.py`, and `shell_tools.py` are pure Python wrappers—keep them synchronous and text-only so streaming stdout remains readable.
- `image_tools.load_image` shows how to emit both a confirmation `ToolMessage` and a follow-up `HumanMessage` containing a base64 image to trigger the multimodal route; it also demonstrates MIME detection for remote URLs.
- `web_tools.readable_web_get` fetches HTML with a desktop UA, runs it through `html2text`, analyzes headings (`mrkdwn_analysis`), and stores the full markdown as a `DataEntry` (keyed by `markdown_<hash>`) in both agent state (`stored_data`) and the global `data_store` helpers. Follow that pipeline when adding extraction helpers, and remember the data-store APIs take only `data_id`—do not pass the LangGraph runtime object.
- `data_store.py` remains the single source of truth for persisted blobs; it has convenience functions for listing, deleting, and size reporting that newer LangChain tools should reuse for consistency.

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

## Conventions & Pitfalls
- Tool descriptions must stay concise; long outputs should be summarized or stored via `data_store` + metadata so context stays under the router threshold.
- `execute_shell_command` executes with full user privileges and only a 30s timeout—guard against destructive commands and prefer idempotent operations when authoring plans or examples.
- Task tools (`task_tools.py`) are Phase-3 placeholders and excluded from the active tool list; avoid relying on them until the sub-agent workflow lands.
- Because Phoenix auto-instrumentation hooks every LangChain call, avoid spawning parallel event loops or threads inside tools; stick to synchronous IO or wrap network calls with clear timeouts.
- Streaming happens directly on stdout; if you add additional prints/logging inside tools or middleware, keep them terse so they do not interleave confusingly with model tokens.

## Go-To Files
- High-level design notes still live in `CLAUDE.md` and Phase docs referenced in `QUICK_START.md`—consult them before reworking routing or tool behaviors.
- `langchain_middleware.py`, `langchain_state.py`, and `langchain_tools/README.md` capture the latest migration conventions; keep new work aligned with those patterns to avoid regressing back to the legacy tool router.
