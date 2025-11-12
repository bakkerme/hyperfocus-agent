# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Hyperfocus-Agent is a Python CLI tool that creates an AI agent capable of executing tools via a local LM Studio language model (OpenAI-compatible API). The agent interprets user requests and calls various tools to perform file operations, directory operations, and utility functions.

## Commands

### Running the Agent
```bash
poetry run hyperfocus
```

### Development Setup
```bash
# Install dependencies
poetry install

# Run the application
poetry run hyperfocus
```

### Adding Dependencies
```bash
poetry add some_dependency
```

## Architecture

### Core Design Pattern: Security-First Tool Router

The project uses a **whitelist-based tool execution architecture** with three layers:

1. **Entry Point** (`main.py`): Orchestrates the workflow
   - Connects to LM Studio at hardcoded endpoint (`http://100.89.244.102:1234/v1`)
   - Aggregates tool definitions from all modules
   - Processes LLM responses and routes tool calls to execution layer

2. **Execution Layer** (`tool_router.py`): Safe tool execution
   - `TOOL_REGISTRY`: Whitelist mapping tool names to implementations
   - `execute_tool_call()`: Securely executes single tool with JSON argument parsing
   - `execute_tool_calls()`: Batch executor with isolated error handling
   - **Security**: Uses `json.loads()` (not `eval()`), validates function signatures, returns structured results

3. **Tool Modules**: Category-specific implementations and definitions
   - Each module provides both implementations AND OpenAI tool definitions
   - Keeps definitions synchronized with implementations by design

### Module Responsibilities

- **tool_router.py**: The security boundary - ALL tool execution goes through `TOOL_REGISTRY`
  - Automatic large result detection and storage
  - Configurable size threshold via `MAX_TOOL_RESULT_SIZE` env var
- **directory_ops.py**: Directory operations (list, create, change, get current)
- **file_ops.py**: File operations (read, create, append)
- **shell_ops.py**: Shell command execution
- **web_ops.py**: Web scraping and HTTP operations
- **image_ops.py**: Multi-modal image loading and processing
- **task_ops.py**: Task execution system for processing large data
  - `store_data_for_task()`: Store large data for processing
  - `execute_simple_task()`: Run tasks in isolated LLM context
  - `task_orientated_paging()`: Process large data in semantic chunks
- **task_executor.py**: Core task execution engine
  - Jina AI segmenter integration for intelligent chunking
  - Fallback to simple line-based splitting
  - Aggregation strategies: concatenate or summarize
- **llm_router.py**: Intelligent routing between local/remote/multimodal LLMs
- **types.py**: TypedDict definitions for OpenAI function calling schemas

### Type System

The project uses the OpenAI SDK's native types, re-exported through [types.py](src/hyperfocus_agent/types.py) for convenience:

- `ChatCompletionToolParam`: The official OpenAI type for tool definitions (imported from `openai.types.chat`)

All `*_TOOLS` lists must be typed as `list[ChatCompletionToolParam]` to ensure compatibility with the OpenAI SDK and enable proper type checking.

**Important**: Always use the OpenAI SDK's types directly rather than creating custom TypedDict definitions. This ensures your code stays compatible as the SDK evolves.

### Adding New Tools

To add a new tool:

1. Implement the function in the appropriate module (or create new module for new category)
   - Ensure proper type hints for parameters and return values
   - Functions that return values must return on all code paths

2. Add OpenAI tool definition to module's `*_TOOLS` list following the pattern:
   ```python
   from .types import ChatCompletionToolParam

   MY_TOOLS: list[ChatCompletionToolParam] = [
       {
           "type": "function",
           "function": {
               "name": "function_name",
               "description": "What it does",
               "parameters": {
                   "type": "object",
                   "properties": {
                       "param_name": {
                           "type": "string",
                           "description": "Parameter description"
                       }
                   },
                   "required": ["param_name"]
               }
           }
       }
   ]
   ```

3. Register the function in [tool_router.py](src/hyperfocus_agent/tool_router.py)'s `TOOL_REGISTRY` dictionary

4. If new module: import and add to tool aggregation in [main.py](src/hyperfocus_agent/main.py)

**Important**: The type annotation `list[ChatCompletionToolParam]` is required for type safety. This ensures your tool definitions are compatible with the OpenAI SDK's type expectations.

### Important Design Decisions

**Hardcoded LM Studio Configuration**: The LM Studio endpoint and model are hardcoded in `main.py`:
- IP: `100.89.244.102:1234`
- Model: `qwen/qwen3-30b-a3b-2507`
- Not currently environment-configurable

**Direct Filesystem Access**: Tools operate with full user permissions without:
- Sandboxing or path validation
- Path restriction checks
- Working directory constraints

**Error Isolation**: Tool router ensures one failed tool call doesn't break others - each call is isolated with comprehensive error handling.

**Task System for Large Data**: When tool results exceed `MAX_TOOL_RESULT_SIZE` (default 20k chars):
- Data is automatically stored with a generated ID
- LLM receives guidance on how to process the large data
- Available tools: `task_orientated_paging` for chunked processing, `execute_simple_task` for isolated execution
- Uses Jina AI segmenter (if `JINA_API_KEY` set) for intelligent semantic chunking
- Falls back to line-based splitting if Jina unavailable

## Data Store

The project includes a generic data store ([data_store.py](src/hyperfocus_agent/data_store.py)) for maintaining state across tool calls. This enables:
- **Stateful web scraping**: Load pages once, extract multiple times
- **Task data storage**: Keep large data for task-based processing
- **Cross-tool data sharing**: Any tool can store/retrieve data

**Key Functions:**
- `store_data(data_id, content, data_type, metadata)`: Store typed data with metadata
- `retrieve_data(data_id)`: Retrieve stored content
- `data_exists(data_id)`: Check if data exists
- `get_data_info(data_id)`: Get metadata without content
- `list_stored_data()`: List all stored data

## Task System

The task system enables processing data that exceeds context window limits. See [TASK_SYSTEM.md](TASK_SYSTEM.md) for detailed documentation.

**Key Features:**
- **Isolated execution**: Tasks run without chat history to save context
- **Intelligent chunking**: Jina AI segmenter creates semantic chunks (optional)
- **Automatic triggering**: Large tool results auto-trigger task storage
- **Flexible aggregation**: Concatenate or summarize results across chunks

**Workflow Example:**
```python
# 1. Agent reads large file (auto-stored if > 20k chars)
read_file("large_log.txt") → Returns guidance with data_id

# 2. Agent processes with task system
task_orientated_paging(
    data_id="read_file_abc123",
    task="Extract all ERROR messages",
    aggregation_strategy="summarize"
)
```

**Configuration:**
- `JINA_API_KEY`: Enable semantic chunking (recommended)
- `MAX_TOOL_RESULT_SIZE`: Size threshold for auto-storage (default: 20000)
- Task page size: Configurable per-call (default: 15000)

## Web Scraping

The project provides stateful web scraping capabilities for multi-step data extraction. See [WEB_SCRAPING.md](WEB_SCRAPING.md) for detailed documentation.

**Three-tier approach:**
1. **Simple**: `readable_web_get()` - Convert page to markdown
2. **Analysis**: `get_dom_skeleton()` - Generate hyper-condensed DOM tree with headings
3. **Stateful**: Load page → Design selectors → Extract with CSS/XPath

**Workflow Example:**
```python
# 1. Load page and get DOM skeleton
load_page_for_navigation("https://news.ycombinator.com", page_id="hn")

# 2. Extract data with CSS selectors
titles = extract_with_css(
    page_id="hn",
    selector="tr.athing td.title span.titleline a",
    extract_type="text"
)

# 3. Extract with XPath for complex queries
links = extract_with_xpath(
    page_id="hn",
    xpath="//tr[@class='athing']//a[@href]",
    extract_type="attrs"
)
```

**Key Features:**
- **DOM Skeleton**: Hyper-condensed tree view with headings preserved
- **Stateful**: Load once, extract multiple times (saves bandwidth/time)
- **CSS & XPath**: Both selector types supported
- **Multiple extract types**: text, html, or attributes
- **Integration**: Works with task system for large extractions

## Project Structure

```
src/hyperfocus_agent/
├── __init__.py          # Package interface, exports main()
├── main.py              # Entry point, LLM orchestration
├── llm_router.py        # Routes between local/remote/multimodal LLMs
├── tool_router.py       # Security layer, TOOL_REGISTRY, auto-storage
├── types.py             # TypedDict definitions for OpenAI schemas
├── agent.py             # System prompts and agent configuration
├── data_store.py        # Generic in-memory data store for stateful operations
├── directory_ops.py     # Directory tools + definitions
├── file_ops.py          # File tools + definitions
├── shell_ops.py         # Shell command tools + definitions
├── web_ops.py           # Web scraping tools + definitions (DOM, CSS, XPath)
├── image_ops.py         # Multi-modal image tools + definitions
├── task_ops.py          # Task system tools + definitions
├── task_executor.py     # Task execution engine with Jina integration
└── utils.py             # Utility tools + definitions
```

## Dependencies

- Python ^3.12 (requires 3.12+)
- openai ^2.6.1 (OpenAI SDK for LM Studio API)
- requests ^2.31.0 (HTTP library for web ops and Jina API)
- beautifulsoup4 ^4.14.2 (HTML parsing for web scraping)
- lxml ^6.0.2 (XML/HTML processing with XPath support)
- html2text ^2025.4.15 (HTML to markdown conversion)
- readability-lxml ^0.8.4.1 (Extract main content from pages)
- Poetry for dependency management

## Environment Variables

See [.env.example](.env.example) for a complete list. Key variables:

**Required:**
- `LOCAL_OPENAI_BASE_URL`, `LOCAL_OPENAI_API_KEY`, `LOCAL_OPENAI_MODEL`
- `REMOTE_OPENAI_BASE_URL`, `REMOTE_OPENAI_API_KEY`, `REMOTE_OPENAI_MODEL`

**Optional:**
- `JINA_API_KEY`: Enable semantic chunking (highly recommended)
- `MULTIMODAL_OPENAI_*`: For vision/image processing capabilities
- `MAX_TOOL_RESULT_SIZE`: Auto-storage threshold (default: 20000)
- `LLM_ROUTER_THRESHOLD`: Switch to remote LLM threshold (default: 10000)
- `LM_TOOL_CALL_ITERATIONS`: Max tool iterations (default: 50)
