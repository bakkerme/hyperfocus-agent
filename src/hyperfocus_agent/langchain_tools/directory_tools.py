"""Directory operations migrated to LangChain @tool decorator pattern.

This module replaces directory_ops.py with LangChain-compatible tools.
"""
import os
from langchain_core.tools import tool


@tool
def list_directory(path: str) -> str:
    """List all files and directories in the specified path.

    Args:
        path: The path to list the contents of

    Returns:
        A formatted list of files and directories
    """
    listing = os.listdir(path)

    # Format as a readable list
    if not listing:
        return f"Directory '{path}' is empty."

    # Sort and format
    dirs = [item for item in listing if os.path.isdir(os.path.join(path, item))]
    files = [item for item in listing if os.path.isfile(os.path.join(path, item))]

    result = [f"Contents of '{path}':"]
    if dirs:
        result.append(f"\nDirectories ({len(dirs)}):")
        result.extend(f"  📁 {d}/" for d in sorted(dirs))
    if files:
        result.append(f"\nFiles ({len(files)}):")
        result.extend(f"  📄 {f}" for f in sorted(files))

    return "\n".join(result)


@tool
def get_current_directory() -> str:
    """Get the current working directory.

    Returns:
        The absolute path of the current working directory
    """
    cwd = os.getcwd()
    return f"Current working directory: {cwd}"


@tool
def change_directory(path: str) -> str:
    """Change the current working directory.

    Args:
        path: The path to change the current directory to

    Returns:
        Confirmation message with the new directory
    """
    os.chdir(path)
    new_cwd = os.getcwd()
    return f"Changed directory to: {new_cwd}"


@tool
def create_directory(path: str) -> str:
    """Create a directory at the specified path.

    Creates parent directories if needed (like mkdir -p).

    Args:
        path: The path where the directory will be created

    Returns:
        Confirmation message
    """
    os.makedirs(path, exist_ok=True)
    abs_path = os.path.abspath(path)
    return f"Directory created: {abs_path}"


# Export tools as a list for easy import
DIRECTORY_TOOLS = [
    list_directory,
    get_current_directory,
    change_directory,
    create_directory
]
