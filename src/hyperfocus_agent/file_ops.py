"""File operations and related tool definitions."""
from .types import ChatCompletionToolParam, ToolResult


def read_file(path: str) -> ToolResult:
    """Read and return the contents of a file."""
    with open(path, 'r') as f:
        content = f.read()
    return {
        "data": content,
        "include_in_context": True  # File contents should stay in context by default
    }


def create_file_with_content(path: str, content: str) -> ToolResult:
    """Create a file at the specified path with the given content."""
    with open(path, 'w') as f:
        f.write(content)
    return {
        "data": f"File '{path}' created with content.",
        "include_in_context": True
    }


def append_to_file(path: str, content: str) -> ToolResult:
    """Append content to an existing file."""
    with open(path, 'a') as f:
        f.write(content)
    return {
        "data": f"Content appended to file '{path}'.",
        "include_in_context": True
    }


# Tool definitions for file operations
FILE_TOOLS: list[ChatCompletionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path of the file to read"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file_with_content",
            "description": "Creates a file at the specified path with the given content",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path where the file will be created"
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write into the file"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "append_to_file",
            "description": "Appends content to a file at the specified path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path of the file to append to"
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to append to the file"
                    }
                },
                "required": ["path", "content"]
            }
        }
    }
]
