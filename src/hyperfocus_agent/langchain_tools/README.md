# LangChain Tools

This directory contains tools migrated to use LangChain's `@tool` decorator pattern.

## Migration Status (Phase 2)

- [ ] **file_tools.py** - File operations (read_file, create_file, append_to_file)
- [ ] **directory_tools.py** - Directory operations (list_directory, create_directory, change_directory, get_current_directory)
- [ ] **shell_tools.py** - Shell command execution (execute_shell_command)
- [ ] **web_tools.py** - Web scraping (readable_web_get, get_readable_web_section, retrieve_stored_readable_web_section)
- [ ] **image_tools.py** - Multi-modal operations (load_image)
- [ ] **task_tools.py** - Task execution (store_data_for_task, execute_simple_task, task_orientated_paging)

## Tool Pattern

Each tool follows this pattern:

```python
from langchain.tools import tool, ToolRuntime
from langgraph.types import Command
from ..langchain_state import HyperfocusState, HyperfocusContext

@tool
def example_tool(
    param: str,
    runtime: ToolRuntime[HyperfocusContext, HyperfocusState]
) -> Command:
    """Tool description for the LLM.

    Args:
        param: Parameter description
    """
    # Execute tool logic
    result = do_something(param)

    # Determine if should be included in context
    include_in_context = len(result) < MAX_SIZE

    # Store metadata for context builder middleware
    metadata = {
        "include_in_context": include_in_context,
        "function_name": "example_tool",
        "created_at_iteration": runtime.state["current_iteration"],
        "stub_message": f"[Result from example_tool excluded]"
    }

    # Return Command to update state
    return Command(
        update={
            "tool_result_metadata": {
                **runtime.state["tool_result_metadata"],
                runtime.tool_call_id: metadata
            },
            "messages": [
                ToolMessage(
                    content=result if include_in_context else metadata.get("context_guidance", "Result stored"),
                    tool_call_id=runtime.tool_call_id,
                    name="example_tool",
                    artifact={"full_result": result}  # Store full data in artifact
                )
            ]
        }
    )
```

## Key Differences from Original

1. **@tool decorator** replaces OpenAI tool definitions
2. **ToolRuntime parameter** provides access to state and context
3. **Command return** updates state instead of returning dict
4. **ToolMessage.artifact** stores large data without sending to LLM
5. **Metadata stored in state** via Command.update instead of separate tracking

## Testing

Each tool module should have corresponding tests in `tests/langchain_tools/test_<module>.py` that verify:
- Tool function executes correctly
- Metadata is stored properly
- Large results trigger stubbing
- Context guidance is provided when needed
