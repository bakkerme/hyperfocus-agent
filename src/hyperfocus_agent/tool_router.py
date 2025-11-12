"""Tool routing system for securely mapping tool calls to function implementations."""
import json
import os
import hashlib
from typing import Callable, Any

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
    get_readable_web_section,
    retrieve_stored_readable_web_section
)
from .image_ops import load_image
from .task_ops import (
    store_data_for_task,
    execute_simple_task,
    task_orientated_paging
)


# Registry mapping tool names to their actual function implementations
TOOL_REGISTRY: dict[str, Callable] = {
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
    "get_readable_web_section": get_readable_web_section,
    "retrieve_stored_readable_web_section": retrieve_stored_readable_web_section,

    # Image operations
    "load_image": load_image,

    # Task operations
    "store_data_for_task": store_data_for_task,
    "execute_simple_task": execute_simple_task,
    "task_orientated_paging": task_orientated_paging
}


# Configuration for automatic large result handling
# Configurable via environment variable, default to 20k characters (~5k tokens)
MAX_RESULT_SIZE = int(os.getenv("MAX_TOOL_RESULT_SIZE", "20000"))

# Tools that commonly return large results and should trigger auto-storage
LARGE_RESULT_TOOLS = {
    "read_file",
    "execute_shell_command",
    "readable_web_get",
    "list_directory"  # Can be large for big directories
}


def _generate_data_id(function_name: str, arguments: str) -> str:
    """
    Generate a unique data ID based on the function and its arguments.

    Args:
        function_name: Name of the tool that was called
        arguments: JSON string of arguments

    Returns:
        A unique identifier for this data
    """
    # Create a short hash of the arguments for uniqueness
    arg_hash = hashlib.md5(arguments.encode()).hexdigest()[:8]
    return f"{function_name}_{arg_hash}"


def _handle_large_result(result: Any, function_name: str, arguments: str) -> dict[str, Any]:
    """
    Handle a result that's too large to return directly.
    Automatically stores it and returns guidance to the LLM.

    Args:
        result: The large result from the tool execution
        function_name: Name of the tool that produced the result
        arguments: JSON string of the arguments used

    Returns:
        Dictionary with storage info and guidance for the LLM
    """
    result_str = str(result)
    data_id = _generate_data_id(function_name, arguments)

    # Store the data automatically
    store_data_for_task(data_id, result_str)

    # Parse arguments to show what was requested
    try:
        args_dict = json.loads(arguments)
        args_summary = ", ".join(f"{k}={v}" for k, v in args_dict.items())
    except:
        args_summary = arguments

    # Create a helpful guidance message
    guidance = {
        "message": f"⚠️ Result too large ({len(result_str)} characters)",
        "data_id": data_id,
        "data_size": len(result_str),
        "tool_used": function_name,
        "arguments": args_summary,
        "preview": result_str[:500] + "..." if len(result_str) > 500 else result_str,
        "guidance": {
            "what_happened": f"The result from {function_name} was automatically stored because it exceeds {MAX_RESULT_SIZE} characters.",
            "available_tools": [
                {
                    "tool": "task_orientated_paging",
                    "description": "Process this large data in pages with a specific task",
                    "example": f'task_orientated_paging(data_id="{data_id}", task="Your analysis task here", aggregation_strategy="summarize")'
                },
                {
                    "tool": "execute_simple_task",
                    "description": "If the data actually fits in context, process it directly (no paging)",
                    "note": "Use the stored data_id to retrieve: you'll need to get it from the store first"
                }
            ],
            "recommended_action": f"Use task_orientated_paging with data_id='{data_id}' to analyze this data in manageable chunks."
        }
    }

    return guidance


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

        # Check if result is too large and should be auto-stored
        # Skip this check for task operations (they handle large data themselves)
        if function_name not in {"store_data_for_task", "execute_simple_task", "task_orientated_paging"}:
            result_str = str(result)

            # If result is large and from a tool that commonly produces large output
            if len(result_str) > MAX_RESULT_SIZE and function_name in LARGE_RESULT_TOOLS:
                return _handle_large_result(result, function_name, tool_call.function.arguments)

        return result
    except TypeError as e:
        raise TypeError(f"Invalid arguments for {function_name}: {e}")


def execute_tool_calls(tool_calls) -> list:
    """
    Execute multiple tool calls and return their results.

    Args:
        tool_calls: List of tool call objects from the LLM response

    Returns:
        List of results from executing each tool call. Each result includes:
        - tool_call_id: ID of the tool call
        - function_name: Name of the function executed
        - arguments: JSON string of arguments
        - result: The result data (if success=True)
        - error: Error message (if success=False)
        - success: Whether execution succeeded
        - include_in_context: Whether to include full result in next context (default: True)
        - stub_message: Custom message when excluded from context (optional)
    """
    results = []
    for tool_call in tool_calls:
        try:
            result = execute_tool_call(tool_call)

            # Handle standardized ToolResult format
            # Check if this is a ToolResult dict with 'data' field

            # New standardized format
            include_in_context = result.get("include_in_context", True)
            stub_message = result.get("stub_message", f"[{tool_call.function.name} result from previous iteration]")
            context_guidance = result.get("context_guidance")
            result_data = result["data"]

            result_dict = {
                "tool_call_id": tool_call.id,
                "function_name": tool_call.function.name,
                "arguments": tool_call.function.arguments,
                "result": result_data,
                "success": True,
                "include_in_context": include_in_context,
                "stub_message": stub_message
            }

            # Add context_guidance if provided
            if context_guidance:
                result_dict["context_guidance"] = context_guidance

            results.append(result_dict)
        except Exception as e:
            results.append({
                "tool_call_id": tool_call.id,
                "function_name": tool_call.function.name,
                "arguments": tool_call.function.arguments,
                "error": str(e),
                "success": False,
                "include_in_context": True,  # Always include errors in context
                "stub_message": f"[Error from {tool_call.function.name}]"
            })
    return results
