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
- **directory_ops.py**: Directory operations (list, create, change, get current)
- **file_ops.py**: File operations (read, create, append)
- **utils.py**: Utility functions (say_hello demo)

### Adding New Tools

To add a new tool:

1. Implement the function in the appropriate module (or create new module for new category)
2. Add OpenAI tool definition to module's `*_TOOLS` list following the pattern:
   ```python
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
   ```
3. Register the function in `tool_router.py`'s `TOOL_REGISTRY` dictionary
4. If new module: import and add to tool aggregation in `main.py`

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

## Project Structure

```
src/hyperfocus_agent/
├── __init__.py          # Package interface, exports main()
├── main.py              # Entry point, LLM orchestration
├── tool_router.py       # Security layer, TOOL_REGISTRY, execution
├── directory_ops.py     # Directory tools + definitions
├── file_ops.py          # File tools + definitions
└── utils.py             # Utility tools + definitions
```

## Dependencies

- Python ^3.12 (requires 3.12+)
- openai ^2.6.1 (OpenAI SDK for LM Studio API)
- Poetry for dependency management
