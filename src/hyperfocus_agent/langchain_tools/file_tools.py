"""File operations migrated to LangChain @tool decorator pattern.

This module replaces file_ops.py with LangChain-compatible tools.
Each tool uses the @tool decorator and returns results that work with
the conditional context middleware.
"""
from typing import Annotated
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage

# For future phases when we implement ToolRuntime
# from langgraph.prebuilt import ToolRuntime
# from ..langchain_state import HyperfocusState, HyperfocusContext


@tool
def read_file(path: str) -> str:
    """Read and return the contents of a file.

    Args:
        path: The path of the file to read

    Returns:
        The contents of the file as a string, or an error message for binary files
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except UnicodeDecodeError:
        # File is binary, return a helpful message
        import os
        file_size = os.path.getsize(path)
        return f"Error: '{path}' is a binary file ({file_size} bytes). Cannot read as text. Use image analysis tools for images or other specialized tools for binary files."

@tool
def create_file_with_content(path: str, content: str) -> str:
    """Create a file at the specified path with the given content.

    Args:
        path: The path where the file will be created
        content: The content to write into the file

    Returns:
        Confirmation message
    """
    with open(path, 'w') as f:
        f.write(content)

    return f"File '{path}' created with {len(content)} characters."


@tool
def append_to_file(path: str, content: str) -> str:
    """Append content to an existing file.

    Args:
        path: The path of the file to append to
        content: The content to append to the file

    Returns:
        Confirmation message
    """
    with open(path, 'a') as f:
        f.write(content)

    return f"Appended {len(content)} characters to file '{path}'."


# Export tools as a list for easy import
FILE_TOOLS = [
    read_file,
    create_file_with_content,
    append_to_file
]
