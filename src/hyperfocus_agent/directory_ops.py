"""Directory operations and related tool definitions."""
import os
from .types import ChatCompletionToolParam, ToolResult


def list_directory(path: str) -> ToolResult:
    """List all files and directories in the specified path."""
    listing = os.listdir(path)
    return {
        "data": listing,
        "include_in_context": True
    }


def get_current_directory() -> ToolResult:
    """Get the current working directory."""
    cwd = os.getcwd()
    return {
        "data": cwd,
        "include_in_context": True
    }


def change_directory(path: str) -> ToolResult:
    """Change the current working directory."""
    os.chdir(path)
    return {
        "data": f"Changed current directory to '{path}'.",
        "include_in_context": True
    }


def create_directory(path: str) -> ToolResult:
    """Create a directory at the specified path."""
    os.makedirs(path, exist_ok=True)
    return {
        "data": f"Directory '{path}' created.",
        "include_in_context": True
    }


# Tool definitions for directory operations
DIRECTORY_TOOLS: list[ChatCompletionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lists all files and directories in the specified path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to list the contents of"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_directory",
            "description": "Gets the current working directory",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "change_directory",
            "description": "Changes the current working directory to the specified path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to change the current directory to"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Creates a directory at the specified path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path where the directory will be created"
                    }
                },
                "required": ["path"]
            }
        }
    }
]
