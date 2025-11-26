# GEMINI.md

This file provides guidance to Gemini models when working with code in this repository.

## Project Overview

Hyperfocus-Agent is a Python CLI tool that creates an AI agent capable of executing tools using LangChain. The agent is designed to be powered by local or remote OpenAI-compatible APIs (like LM Studio or custom endpoints). It interprets user requests and calls various tools to perform file operations, directory operations, shell commands, and web scraping.

## Commands

### Running the Agent
```bash
poetry run hyperfocus "Your request to the agent"
```

### Development Setup
```bash
# Install dependencies
poetry install

# Run the application
poetry run hyperfocus "Your request"
```

### Adding Dependencies
```bash
poetry add some_dependency
```

## Architecture

### Core Design Pattern: LangChain Agent with Middleware

The project is built on LangChain's `create_agent` function, which constructs a conversational agent using a set of tools and a core prompt. It uses `langgraph` for managing the agent's state and execution flow, with an in-memory checkpointer for conversation history.

1.  **Entry Point** (`main.py`):
    *   Parses the user's command-line message.
    *   Initializes observability with Arize Phoenix for tracing.
    *   Calls `create_hyperfocus_agent()` to build the agent.
    *   Invokes the agent with the user message and prints the final response.

2.  **Agent Factory** (`langchain_agent.py`):
    *   `create_hyperfocus_agent()` is the central factory for building the agent.
    *   It loads model configurations from the environment using `ModelConfig`.
    *   It aggregates all available tools from the `langchain_tools` directory.
    *   It configures and applies a chain of middleware to enhance the agent's capabilities.

3.  **Model Configuration** (`model_config.py`):
    *   `ModelConfig.from_environment()` loads credentials for `LOCAL`, `REMOTE`, and `MULTIMODAL` models from environment variables.
    *   It creates `ChatOpenAI` instances for each model. This is where you can configure parameters like temperature and streaming.

4.  **State Management** (`langchain_state.py`):
    *   `HyperfocusState` and `HyperfocusContext` define the schemas for the agent's internal state and the context passed between steps, built on top of `langgraph`.

5.  **Tool Modules** (`langchain_tools/`):
    *   Each file (e.g., `file_tools.py`, `shell_tools.py`) defines a set of related tools using the `@tool` decorator from LangChain.
    *   This makes tools self-contained and easy to manage.

### Middleware Chain

The agent uses several custom middleware functions (defined in `src/hyperfocus_agent/middleware/`) to pre-process and post-process messages and tool calls. The order is important:

1.  `filter_old_script_versions`: Removes previous, outdated calls to `create_python_script` for the same file path to avoid redundant operations.
2.  `strip_processed_images`: Removes image data from messages after they have been processed by a tool.
3.  `dynamic_model_selection`: Intelligently routes the execution to the appropriate LLM (local, remote, or multimodal) based on the content of the messages (e.g., presence of images).
4.  `log_tool_execution`: Logs tool calls and their arguments for debugging and observability.
5.  `available_tools`: A middleware to inform the agent about the available tools.

### Adding New Tools

To add a new tool:

1.  **Implement the function** in the appropriate module within `src/hyperfocus_agent/langchain_tools/`.
    *   Decorate the function with `@tool`.
    *   Use clear type hints for all arguments. LangChain uses these to generate the tool's JSON schema.

    ```python
    from langchain.tools import tool

    @tool
    def my_new_tool(param1: str, param2: int) -> str:
        """
        A clear docstring explaining what the tool does, its parameters, and what it returns.
        This docstring is visible to the LLM.
        """
        # ... implementation ...
        return "Result"
    ```

2.  **Register the tool**: Add the new tool function to the list of exported tools at the bottom of the file.

    ```python
    # In src/hyperfocus_agent/langchain_tools/my_tools.py
    MY_NEW_TOOLS = [my_new_tool]
    ```

3.  **Aggregate the tool**: In `src/hyperfocus_agent/langchain_agent.py`, import your new tool list and add it to the `all_tools` list.

    ```python
    # In src/hyperfocus_agent/langchain_agent.py
    from .langchain_tools.my_tools import MY_NEW_TOOLS

    # ...
    all_tools = [
        *DIRECTORY_TOOLS,
        *FILE_TOOLS,
        # ... other tools
        *MY_NEW_TOOLS, # Add your new tools here
    ]
    ```

## Project Structure

```
src/hyperfocus_agent/
├── __init__.py
├── main.py              # Main CLI entry point
├── langchain_agent.py   # Agent factory and middleware setup
├── langchain_state.py   # LangGraph state definitions
├── model_config.py      # Loads LLM configurations from environment
├── ocr.py               # Standalone OCR script/tool
├── prompts.py           # System prompts for the agent
├── langchain_tools/     # Directory for all LangChain tools
│   ├── file_tools.py
│   ├── shell_tools.py
│   └── ...
└── middleware/          # Custom agent middleware
    ├── context_middleware.py
    ├── image_middleware.py
    └── ...
```

## Dependencies

- **Python**: >=3.12
- **LangChain**: `langchain`, `langgraph`, `langchain-openai` for the core agent framework.
- **OpenAI**: The `openai` library for API interaction.
- **Arize Phoenix**: `arize-phoenix-otel` for observability and tracing.
- **ripgrepy**: For fast, file content searching.

## Environment Variables

The agent is configured entirely through environment variables.

**Required:**
- `LOCAL_OPENAI_BASE_URL`, `LOCAL_OPENAI_API_KEY`, `LOCAL_OPENAI_MODEL`: Credentials for the primary, local model.
- `REMOTE_OPENAI_BASE_URL`, `REMOTE_OPENAI_API_KEY`, `REMOTE_OPENAI_MODEL`: Credentials for a more powerful, remote model.

**Optional:**
- `MULTIMODAL_OPENAI_BASE_URL`, `MULTIMODAL_OPENAI_API_KEY`, `MULTIMODAL_OPENAI_MODEL`: Credentials for a vision-capable model.
- `LLM_ROUTER_THRESHOLD`: Token threshold to switch from the local to the remote LLM (default: 10000).
- `PHOENIX_COLLECTOR_ENDPOINT`: The URL for the Phoenix tracing collector (default: `http://localhost:6006`).
