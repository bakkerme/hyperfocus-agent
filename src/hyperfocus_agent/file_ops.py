"""File operations and related tool definitions."""


def read_file(path: str) -> str:
    """Read and return the contents of a file."""
    with open(path, 'r') as f:
        content = f.read()
    return content


def create_file_with_content(path: str, content: str) -> str:
    """Create a file at the specified path with the given content."""
    with open(path, 'w') as f:
        f.write(content)
    return f"File '{path}' created with content."


def append_to_file(path: str, content: str) -> str:
    """Append content to an existing file."""
    with open(path, 'a') as f:
        f.write(content)
    return f"Content appended to file '{path}'."


# Tool definitions for file operations
FILE_TOOLS = [
    {
        
    },
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
