"""File operations migrated to LangChain @tool decorator pattern.

This module replaces file_ops.py with LangChain-compatible tools.
Each tool uses the @tool decorator and returns results that work with
the conditional context middleware.
"""
from typing import Annotated
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage

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

@tool
def check_file_exists(path: str) -> str:
    """Check if a file exists at the specified path.

    Args:
        path: The path of the file to check
    Returns:
        Message indicating whether the file exists or not
    """
    import os
    if os.path.exists(path):
        return f"File '{path}' exists."
    else:
        return f"File '{path}' does not exist."

@tool # possible progression options -> validate code on write
def create_python_script(path: str, content: str) -> str:
    """Create a Python script file at the specified path with the given content.
    Libraries available:
        Python standard library
        beautifulsoup4

    Args:  
        path: The path where the Python script will be created
            content: The Python code to write into the script
        content: The content to write into the file

    Returns:
        Confirmation message
    """
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

    return f"Python script '{path}' created with {len(content)} characters."

# Export tools as a list for easy import
FILE_TOOLS = [
    read_file,
    create_file_with_content,
    append_to_file,
    create_python_script
]
