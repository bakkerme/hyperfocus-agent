"""Tool routing system for securely mapping tool calls to function implementations."""
import json
from typing import Callable, Any, Dict

from hyperfocus_agent.web_ops import readable_web_get
from .directory_ops import (
    list_directory,
    get_current_directory,
    change_directory,
    create_directory
)
from .file_ops import (
    read_file,
    create_file_with_content,
    append_to_file
)
from .shell_ops import execute_shell_command
from .web_ops import (
    readable_web_get,
    raw_web_get
)
from .utils import say_hello


# Registry mapping tool names to their actual function implementations
TOOL_REGISTRY: dict[str, Callable] = {
    # Utility functions
    "say_hello": say_hello,
    
    # Directory operations
    "list_directory": list_directory,
    "get_current_directory": get_current_directory,
    "change_directory": change_directory,
    "create_directory": create_directory,
    
    # File operations
    "read_file": read_file,
    "create_file_with_content": create_file_with_content,
    "append_to_file": append_to_file,

    # Shell operations
    "execute_shell_command": execute_shell_command,

    # Web operations
    "readable_web_get": readable_web_get,
    "raw_web_get": raw_web_get
}


def execute_tool_call(tool_call) -> Any:
    """
    Securely execute a tool call by routing it to the appropriate function.
    
    Args:
        tool_call: The tool call object from the LLM response
        
    Returns:
        The result of the function execution
        
    Raises:
        ValueError: If the tool name is not registered
        json.JSONDecodeError: If the arguments cannot be parsed
        TypeError: If the function arguments are invalid
    """
    function_name = tool_call.function.name
    
    # Check if the function is registered
    if function_name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {function_name}")
    
    # Parse arguments safely using json.loads instead of eval
    try:
        arguments = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Failed to parse arguments for {function_name}: {e.msg}",
            e.doc,
            e.pos
        )
    
    # Get the function from the registry
    func = TOOL_REGISTRY[function_name]
    
    # Execute the function with the parsed arguments
    try:
        result = func(**arguments)
        return result
    except TypeError as e:
        raise TypeError(f"Invalid arguments for {function_name}: {e}")


def execute_tool_calls(tool_calls) -> list:
    """
    Execute multiple tool calls and return their results.
    
    Args:
        tool_calls: List of tool call objects from the LLM response
        
    Returns:
        List of results from executing each tool call
    """
    results = []
    for tool_call in tool_calls:
        try:
            result = execute_tool_call(tool_call)
            results.append({
                "tool_call_id": tool_call.id,
                "function_name": tool_call.function.name,
                "arguments": tool_call.function.arguments,
                "result": result,
                "success": True
            })
        except Exception as e:
            results.append({
                "tool_call_id": tool_call.id,
                "function_name": tool_call.function.name,
                "arguments": tool_call.function.arguments,
                "error": str(e),
                "success": False
            })
    return results
