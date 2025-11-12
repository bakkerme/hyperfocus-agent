# Complete LangChain Migration Plan

## Executive Summary

This plan outlines a complete migration from your custom framework + OpenAI library to LangChain/LangGraph. The migration will preserve all existing functionality while leveraging LangChain's middleware, state management, and tool execution patterns.

---

## Current Architecture Analysis

### Core Components (15 files)
- **main.py** (236 lines): Entry point, orchestration loop, Phoenix tracing
- **agent.py** (25 lines): System prompts
- **llm_router.py** (218 lines): Local/remote/multimodal LLM routing by context size
- **context_builder.py** (95 lines): Conditional context inclusion with iteration tracking
- **tool_router.py** (257 lines): Whitelist-based tool execution + auto-storage for large results
- **task_executor.py** (181 lines): Isolated LLM tasks with paging + Jina segmentation
- **data_store.py**: In-memory state store
- **Tool modules**: 6 modules (directory_ops, file_ops, shell_ops, web_ops, image_ops, task_ops)

### Key Features to Preserve
1. **Conditional context management** - Tools control their visibility in future iterations
2. **Iteration-based stubbing** - Results shown in full initially, then stubbed
3. **Auto-storage** - Large results (>20k chars) automatically stored
4. **LLM routing** - Switch between local/remote/multimodal based on context size
5. **Task system** - Isolated execution with paging for large data
6. **Multi-modal support** - Image loading and vision capabilities
7. **Web scraping** - Stateful page loading with DOM skeleton extraction
8. **Phoenix observability** - Tracing integration

---

## LangChain Architecture Design

### 1. Custom State Schema

```python
from langchain.agents import AgentState
from typing import Annotated
from langgraph.graph import add_messages

class HyperfocusState(AgentState):
    """Extended agent state for Hyperfocus."""

    # Built-in messages list (required)
    messages: Annotated[list, add_messages]

    # Custom state fields
    current_iteration: int = 0
    tool_result_metadata: dict[str, dict] = {}

    # LLM routing context
    use_multimodal: bool = False

    # Task execution context
    stored_data: dict[str, Any] = {}  # Could also use LangGraph Store
```

### 2. Middleware Stack

```python
from langchain.agents import create_agent
from langchain.agents.middleware import (
    before_model,
    after_model,
    wrap_model_call,
    dynamic_prompt
)

# 1. Context Builder Middleware (replaces context_builder.py)
@before_model
def conditional_context_middleware(
    state: HyperfocusState,
    runtime: Runtime
) -> dict[str, Any] | None:
    """Implement iteration-based message stubbing."""
    messages = state["messages"]
    current_iteration = state["current_iteration"]
    metadata = state["tool_result_metadata"]

    processed_messages = []
    for msg in messages:
        if msg.type == "tool":
            tool_id = msg.tool_call_id
            meta = metadata.get(tool_id, {})

            created_at = meta.get("created_at_iteration", -1)
            include = meta.get("include_in_context", True)

            # Your logic: stub if not include AND from previous iteration
            should_stub = (not include) and (created_at < current_iteration - 1)

            if should_stub:
                stub_msg = ToolMessage(
                    content=meta.get("stub_message", f"[Result excluded]"),
                    tool_call_id=tool_id,
                    name=msg.name,
                    artifact=meta  # Store full metadata in artifact
                )
                processed_messages.append(stub_msg)
            else:
                processed_messages.append(msg)
        else:
            processed_messages.append(msg)

    return {
        "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *processed_messages]
    }

# 2. LLM Router Middleware (replaces llm_router.py logic)
@wrap_model_call
def llm_routing_middleware(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse]
) -> ModelResponse:
    """Route to local/remote/multimodal LLM based on context."""
    # Check for images first
    if request.state.get("use_multimodal") or _has_image_content(request.messages):
        model = multimodal_model
        print("→ Using MULTIMODAL LLM")
    else:
        # Calculate message length
        total_length = _calculate_message_length(request.messages)
        threshold = int(os.getenv("LLM_ROUTER_THRESHOLD", "10000"))

        if total_length > threshold:
            model = remote_model
            print(f"→ Using REMOTE LLM ({total_length} > {threshold})")
        else:
            model = local_model
            print(f"→ Using LOCAL LLM ({total_length} ≤ {threshold})")

    request = request.override(model=model)
    return handler(request)

# 3. Iteration Tracker (after each turn)
@after_model
def track_iteration(
    state: HyperfocusState,
    runtime: Runtime
) -> dict | None:
    """Increment iteration counter after each model call."""
    return {"current_iteration": state["current_iteration"] + 1}
```

### 3. Tool Migration Pattern

Convert each tool module from OpenAI format to LangChain `@tool` decorator:

**Before (current):**
```python
# file_ops.py
def read_file(file_path: str) -> ToolResult:
    content = Path(file_path).read_text()
    return {
        "data": content,
        "include_in_context": len(content) < MAX_SIZE
    }

FILE_TOOLS: list[ChatCompletionToolParam] = [{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a file...",
        # ...
    }
}]
```

**After (LangChain):**
```python
from langchain.tools import tool, ToolRuntime
from langgraph.types import Command

@tool
def read_file(
    file_path: str,
    runtime: ToolRuntime[HyperfocusContext, HyperfocusState]
) -> Command:
    """Read a file from the filesystem.

    Args:
        file_path: Path to the file to read
    """
    content = Path(file_path).read_text()

    # Determine if should be included in context
    include_in_context = len(content) < MAX_SIZE

    # Store metadata for context builder
    metadata = {
        "include_in_context": include_in_context,
        "function_name": "read_file",
        "created_at_iteration": runtime.state["current_iteration"],
        "stub_message": f"[File {file_path} content from previous iteration]"
    }

    # If large, add context guidance
    if not include_in_context:
        metadata["context_guidance"] = (
            f"File content stored with ID 'read_file_{hash(file_path)}'. "
            "Use task_orientated_paging to process."
        )

    # Return Command to update state
    return Command(
        update={
            "tool_result_metadata": {
                **runtime.state["tool_result_metadata"],
                runtime.tool_call_id: metadata
            },
            "messages": [
                ToolMessage(
                    content=content if include_in_context else metadata["context_guidance"],
                    tool_call_id=runtime.tool_call_id,
                    name="read_file",
                    artifact={"full_content": content}  # Store in artifact
                )
            ]
        }
    )
```

### 4. Task Execution Integration

Task system becomes a sub-agent pattern:

```python
# Create task executor as a separate agent
task_agent = create_agent(
    model=local_model,
    tools=[],  # No tools, just processing
    system_prompt="You are a task executor. Process data according to instructions."
)

@tool
def task_orientated_paging(
    data_id: str,
    task: str,
    page_size: int = 15000,
    aggregation_strategy: str = "concatenate",
    runtime: ToolRuntime
) -> str:
    """Execute task on large data with paging."""

    # Retrieve from state or store
    data = runtime.state.get("stored_data", {}).get(data_id)

    if not data:
        return f"Error: No data found with ID '{data_id}'"

    # Split into pages (could use Jina segmenter here)
    pages = split_into_pages(data, page_size)

    # Process each page with task agent
    results = []
    for i, page in enumerate(pages):
        response = task_agent.invoke({
            "messages": [{
                "role": "user",
                "content": f"{task}\n\n[Page {i+1}/{len(pages)}]\n\n{page}"
            }]
        })
        results.append(response["messages"][-1].content)

    # Aggregate
    if aggregation_strategy == "summarize":
        # Use task agent again to summarize
        combined = "\n\n".join(results)
        summary = task_agent.invoke({
            "messages": [{
                "role": "user",
                "content": f"Summarize these results:\n\n{combined}"
            }]
        })
        return summary["messages"][-1].content
    else:
        return "\n\n--- Page Break ---\n\n".join(results)
```

---

## Migration Phases

### Phase 1: Dependencies & Setup (1-2 days)

**Add to pyproject.toml:**
```toml
[tool.poetry.dependencies]
langchain = "^0.3.0"
langchain-openai = "^0.2.0"
langgraph = "^0.2.0"
langgraph-checkpoint = "^2.0.0"
# Keep existing dependencies
openai = "^2.6.1"  # LangChain uses this
requests = "^2.31.0"
# ... rest unchanged
```

**Create new files:**
- `langchain_agent.py` - New LangChain agent setup
- `langchain_middleware.py` - All middleware functions
- `langchain_tools.py` - Migrated tools with @tool decorator
- `langchain_state.py` - Custom state schema

### Phase 2: Tool Migration (3-5 days)

Migrate tools module by module in this order:
1. **file_ops.py** → Simple, no dependencies
2. **directory_ops.py** → Simple, no dependencies
3. **shell_ops.py** → Simple, no dependencies
4. **web_ops.py** → Medium complexity (data store integration)
5. **image_ops.py** → Requires multimodal state handling
6. **task_ops.py** → Complex (requires sub-agent pattern)

**For each module:**
- Convert function signatures to use `ToolRuntime` parameter
- Replace `ToolResult` dict with `Command` updates
- Store metadata in state via `Command.update`
- Use `ToolMessage.artifact` for large data
- Write unit tests comparing old vs new output

### Phase 3: Core Agent (2-3 days)

**Create the main agent:**
```python
def create_hyperfocus_agent():
    # Initialize models
    local_model = init_chat_model(f"openai:{LOCAL_MODEL}", base_url=LOCAL_BASE_URL)
    remote_model = init_chat_model(f"openai:{REMOTE_MODEL}", base_url=REMOTE_BASE_URL)
    multimodal_model = init_chat_model(f"openai:{MULTIMODAL_MODEL}", base_url=MULTIMODAL_BASE_URL)

    # Import all migrated tools
    from .langchain_tools import (
        read_file, create_file, list_directory,
        execute_shell_command, readable_web_get,
        load_image, task_orientated_paging,
        # ... all tools
    )

    tools = [read_file, create_file, ...]  # List all tools

    # Create agent with middleware
    agent = create_agent(
        model=local_model,  # Default, will be swapped by middleware
        tools=tools,
        state_schema=HyperfocusState,
        middleware=[
            llm_routing_middleware,      # Route LLM
            conditional_context_middleware,  # Stub old results
            track_iteration,              # Increment counter
        ],
        system_prompt=get_base_prompt(),
        checkpointer=InMemorySaver()  # Or PostgresSaver for production
    )

    return agent
```

**New main.py:**
```python
def main():
    # Phoenix setup (unchanged)
    register(...)

    args = parse_args()
    user_message = " ".join(args.message)

    # Create agent
    agent = create_hyperfocus_agent()

    # Single invocation - no manual loop!
    config = {"configurable": {"thread_id": "cli-session"}}

    # Stream mode for real-time output
    for event in agent.stream(
        {"messages": [{"role": "user", "content": user_message}]},
        config,
        stream_mode="messages"
    ):
        # Print assistant messages as they arrive
        if event["type"] == "ai" and event.get("content"):
            print(event["content"], end="", flush=True)
```

**Key changes:**
- No manual `while True` loop - LangChain handles it
- No manual message appending - handled by `add_messages` reducer
- No manual tool execution - handled by agent
- Streaming handled by `stream_mode="messages"`

### Phase 4: Context Builder Migration (1 day)

Replace `context_builder.py` with middleware as shown in Architecture section.

**Testing strategy:**
1. Capture current behavior with integration tests
2. Run same tests with LangChain version
3. Compare message histories at each iteration
4. Verify stubbing happens at correct iterations

### Phase 5: LLM Router Migration (1 day)

Replace `llm_router.py` logic with middleware.

**Key difference:**
- Current: Custom `LLMRouter` class with `complete()` method
- LangChain: Middleware that swaps models via `request.override(model=...)`

**Benefits:**
- Automatic streaming assembly (no manual chunk handling)
- Standard message types (no manual `ChatCompletion` construction)
- Easier testing (mock the middleware)

### Phase 6: Data Store → LangGraph Store (1 day)

**Current:**
```python
# data_store.py - in-memory dict
store_data(data_id, content, data_type, metadata)
retrieve_data(data_id)
```

**LangChain:**
```python
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()

# In tools:
@tool
def store_data_for_task(
    data_id: str,
    data: str,
    runtime: ToolRuntime
):
    """Store data for task processing."""
    runtime.store.put(("task_data",), data_id, data)
    return f"Stored {len(data)} chars with ID '{data_id}'"

# Pass to agent:
agent = create_agent(
    model=model,
    tools=tools,
    store=store  # Now accessible in all tools via runtime.store
)
```

**Benefits:**
- Integrated with agent runtime
- Can use DB-backed stores (Postgres, Redis)
- Automatic persistence across sessions

### Phase 7: Integration Testing (2-3 days)

Create comprehensive test suite:

```python
# tests/test_migration_parity.py
def test_file_read_stubbing():
    """Verify large file results are stubbed after first iteration."""
    # Create test file >20k chars
    # Call agent twice
    # Verify full content in iteration 1, stub in iteration 2

def test_llm_routing():
    """Verify LLM switching based on context size."""
    # Mock local/remote clients
    # Send small request → verify local called
    # Send large request → verify remote called

def test_task_paging():
    """Verify task system processes large data correctly."""
    # Store large data
    # Call task_orientated_paging
    # Verify all pages processed
```

### Phase 8: Gradual Rollout (1 week)

**Week 1: Side-by-side**
- Run both implementations in parallel
- Compare outputs on test suite
- Fix discrepancies

**Week 2: Canary**
- Route 10% of requests to LangChain version
- Monitor Phoenix traces for errors
- Increase to 50% if stable

**Week 3: Full migration**
- Switch to 100% LangChain
- Remove old code
- Update documentation

---

## File Migration Map

| Current File | New File(s) | Status |
|--------------|-------------|---------|
| `main.py` | `langchain_main.py` | Rewrite |
| `agent.py` | `langchain_agent.py` (prompts remain) | Adapt |
| `context_builder.py` | `langchain_middleware.py` (as middleware) | Transform |
| `llm_router.py` | `langchain_middleware.py` (as middleware) | Transform |
| `tool_router.py` | ❌ Delete (LangChain handles this) | Remove |
| `task_executor.py` | `langchain_tasks.py` (as sub-agent) | Refactor |
| `data_store.py` | Use LangGraph `Store` | Replace |
| `types.py` | `langchain_state.py` + use LangChain types | Adapt |
| Tool modules | `langchain_tools/*.py` (one per domain) | Migrate |

---

## Dependency Changes

### Remove
- Manual OpenAI message construction (`ChatCompletionMessageParam`)
- Custom tool registration (`TOOL_REGISTRY`)
- Manual streaming assembly

### Add
```bash
poetry add langchain langchain-openai langgraph langgraph-checkpoint
```

### Keep
- `openai` - LangChain uses this under the hood
- `requests`, `beautifulsoup4`, `lxml` - Web scraping tools
- `arize-phoenix-otel` - Observability (works with LangChain)

---

## Risk Mitigation

### Risk 1: Behavior Changes
**Mitigation:** Comprehensive integration tests comparing old vs new outputs

### Risk 2: Performance Regression
**Mitigation:** Benchmark tool latency before/after, Phoenix tracing for observability

### Risk 3: Lost Features
**Mitigation:** Feature parity checklist:
- ✅ Conditional context inclusion
- ✅ Iteration-based stubbing
- ✅ Auto-storage for large results
- ✅ LLM routing
- ✅ Task paging
- ✅ Multi-modal support
- ✅ Web scraping state

### Risk 4: Breaking Changes in Dependencies
**Mitigation:** Pin exact versions initially:
```toml
langchain = "0.3.7"  # Not ^0.3.0
langgraph = "0.2.45"
```

### Risk 5: Phoenix Compatibility
**Mitigation:** LangChain has native Phoenix support via OpenInference:
```python
from phoenix.otel import register

tracer_provider = register(
    auto_instrument=True,  # Works with LangChain
    project_name="hyperfocus-agent"
)
```

---

## Benefits of Migration

### 1. **Less Code to Maintain**
- **Before:** 1,300+ lines of orchestration logic
- **After:** ~500 lines (middleware + agent setup)
- **Removed:**
  - Manual message loop (100 lines)
  - Tool router (257 lines)
  - Streaming assembly (100 lines)
  - Context building logic (95 lines)

### 2. **Better Abstractions**
- **State management:** Built-in reducers vs manual dict tracking
- **Tool execution:** Automatic error handling vs try/catch everywhere
- **Streaming:** Native support vs manual chunk assembly

### 3. **Production Features**
- **Checkpointing:** Resume conversations across restarts
- **Human-in-the-loop:** Built-in approval workflows
- **Multi-agent:** Native supervisor/sub-agent patterns
- **Observability:** LangSmith integration

### 4. **Community & Ecosystem**
- **Integrations:** 700+ LangChain integrations (vector stores, APIs, etc.)
- **Updates:** Active development vs maintaining custom code
- **Documentation:** Extensive guides vs internal docs

---

## Timeline Summary

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| 1. Setup | 1-2 days | None |
| 2. Tool Migration | 3-5 days | Phase 1 |
| 3. Core Agent | 2-3 days | Phase 2 |
| 4. Context Builder | 1 day | Phase 3 |
| 5. LLM Router | 1 day | Phase 3 |
| 6. Data Store | 1 day | Phase 3 |
| 7. Integration Tests | 2-3 days | Phases 2-6 |
| 8. Gradual Rollout | 1 week | Phase 7 |
| **Total** | **3-4 weeks** | |

---

## Next Steps

1. **Review this plan** - Gather feedback from team
2. **Create feature branch** - `git checkout -b migrate-to-langchain`
3. **Start Phase 1** - Add dependencies, create new file structure
4. **Migrate simplest tool first** - Prove the pattern with `file_ops.py`
5. **Build incrementally** - Keep main branch working, merge pieces gradually

---

## Additional Resources

- [LangChain Python Docs](https://python.langchain.com/docs/introduction/)
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [LangChain Middleware Guide](https://python.langchain.com/docs/concepts/middleware/)
- [Phoenix + LangChain Integration](https://docs.arize.com/phoenix/tracing/integrations/langchain)

---

**Document Version:** 1.0
**Last Updated:** 2025-01-12
**Author:** Claude (Anthropic)
**Status:** Ready for Review
