# Middleware

This directory contains LangChain middleware that processes state before and after model calls.

## Overview

Middleware allows us to:
- **Reduce context bloat** by filtering out irrelevant or redundant messages
- **Route between models** based on content type and size
- **Strip heavy content** like images after they've been processed
- **Log tool calls** for debugging and observability

## Middleware Execution Order

Middleware is executed in the order defined in [langchain_agent.py](../langchain_agent.py):

1. **filter_old_script_versions** (`context_middleware.py`)
   - Removes old `create_python_script` calls for the same path
   - Keeps only the most recent version
   - Prevents context bloat from iterative script development

2. **strip_processed_images** (`image_middleware.py`)
   - Removes image content after the AI has processed it
   - Replaces images with text stubs
   - Allows switching back to non-multimodal models

3. **dynamic_model_selection** (`image_middleware.py`)
   - Routes to multimodal LLM when images are present
   - Routes to remote LLM when context is large
   - Uses local LLM by default

4. **log_tool_execution** (`logging_middleware.py`)
   - Logs all tool calls with their inputs
   - Helps with debugging and observability

5. **SummarizationMiddleware** (LangChain built-in)
   - Summarizes old messages when context gets too large
   - Keeps the most recent N messages
   - Triggered at 20k tokens

## Context Middleware

The context middleware (`filter_old_script_versions`) specifically handles the case where scripts are being iteratively developed.

### Problem

When the agent creates and updates Python scripts multiple times:
```
User: Create a script to scrape prices
AI: [creates script v1]
User: Update it to handle pagination
AI: [creates script v2]
User: Add error handling
AI: [creates script v3]
```

Without filtering, all three versions of the script remain in context, wasting tokens and potentially confusing the model.

### Solution

The middleware:
1. Tracks all `create_python_script` tool calls by their `path` parameter
2. Identifies the most recent call for each unique path
3. Removes older calls and their results from the message history

### Example

**Before filtering:**
```
messages = [
  HumanMessage("Create script"),
  AIMessage(tool_calls=[create_python_script(path="/tmp/scraper.py", content="v1")]),
  ToolMessage("Created /tmp/scraper.py"),
  HumanMessage("Update it"),
  AIMessage(tool_calls=[create_python_script(path="/tmp/scraper.py", content="v2")]),
  ToolMessage("Created /tmp/scraper.py"),
]
```

**After filtering:**
```
messages = [
  HumanMessage("Create script"),
  HumanMessage("Update it"),
  AIMessage(tool_calls=[create_python_script(path="/tmp/scraper.py", content="v2")]),
  ToolMessage("Created /tmp/scraper.py"),
]
```

### Future Enhancements

Potential additions to context middleware:
- Filter old web scraping results (keep only most recent for same URL)
- Remove file read results after a certain age
- Collapse repeated shell command outputs
- Truncate large tool results that haven't been referenced recently

## Testing

Run the middleware tests:
```bash
poetry run python test_context_middleware.py
```

## Adding New Middleware

To add new middleware:

1. Create a function with the appropriate signature
2. Decorate it with `@before_model`, `@after_model`, `@wrap_model_call`, or `@wrap_tool_call`
3. Import it in [langchain_agent.py](../langchain_agent.py)
4. Add it to the middleware list in the correct order

See [LangChain Middleware docs](https://python.langchain.com/docs/how_to/custom_agent_middleware/) for more details.
