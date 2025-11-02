"""Directory operations and related tool definitions."""
import os
from .types import ChatCompletionToolParam


def list_directory(path: str) -> list:
    """List all files and directories in the specified path."""
    return os.listdir(path)


def get_current_directory() -> str:
    """Get the current working directory."""
    return os.getcwd()


def change_directory(path: str) -> str:
    """Change the current working directory."""
    os.chdir(path)
    return f"Changed current directory to '{path}'."


def create_directory(path: str) -> str:
    """Create a directory at the specified path."""
    os.makedirs(path, exist_ok=True)
    return f"Directory '{path}' created."


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
