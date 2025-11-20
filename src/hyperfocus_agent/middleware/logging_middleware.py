from collections.abc import Callable

from langchain.agents.middleware import (
    wrap_tool_call,
)

from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command
import json


@wrap_tool_call
def log_tool_execution(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command]
) -> ToolMessage | Command:
    """Log tool calls with their inputs for debugging and observability.
    
    This middleware logs:
    - Tool name
    - Tool arguments (formatted JSON)
    - Result (truncated if large)
    """
    tool = request.tool
    if tool is None:
        return handler(request)

    tool_name = tool.name
    tool_input = request.tool_call["args"]
    
    # Format the input nicely
    try:
        input_str = json.dumps(tool_input, indent=2)
    except Exception:
        input_str = str(tool_input)
    
    print(f"\n→ [Tool Call] {tool_name}")
    print(f"  Input: {input_str}")
   
    return handler(request)