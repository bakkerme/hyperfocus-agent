"""File operations migrated to LangChain @tool decorator pattern.

This module replaces file_ops.py with LangChain-compatible tools.
Each tool uses the @tool decorator and returns results that work with
the conditional context middleware.
"""
from typing import Annotated
from langchain.tools import tool
from ripgrepy import Ripgrepy, RipGrepNotFound
import re

@tool
def read_file(path: str, offset: int = 0, limit: int = 1024) -> str:
    """Read and return the contents of a file.

    Args:
        path: The path of the file to read

    Returns:
        The contents of the file as a string, or an error message for binary files
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check file size and return error if too large
        if len(content.encode('utf-8')) <= 256 * 1024:
            content_slice = content.encode('utf-8')[offset:offset+limit].decode('utf-8', errors='ignore')
            return content_slice
        else:
            return f"File content ({len(content.encode('utf-8')) / 1024:.1f}KB) exceeds maximum allowed size (256KB). Please use offset and limit parameters to read specific portions of the file, or use the grep_file tool to search for specific content."
    except UnicodeDecodeError:
        # File is binary, return a helpful message
        import os
        file_size = os.path.getsize(path)
        return f"Error: '{path}' is a binary file ({file_size} bytes). Cannot read as text. Use image analysis tools for images or other specialized tools for binary files."
    except FileNotFoundError:
        return f"Error: File '{path}' not found."

@tool
def grep_file(path: str, search_string: str, case_sensitive: bool = False, max_lines: int = 10) -> str:
    """Search for a string in a file and return matching lines.

    Args:
        path: The path of the file to search
        search_string: The string to search for
        case_sensitive: Whether the search should be case sensitive
        max_lines: Maximum number of matching lines to return
    Returns:
        Matching lines as a single string
    """

    try:
        # Escape special regex characters for literal string search
        escaped_pattern = re.escape(search_string)

        # Initialize ripgrepy with the search pattern
        rg = Ripgrepy(escaped_pattern, path, rg_path='/usr/bin/rg')

        # Configure search options
        rg = rg.line_number().max_count(max_lines)

        # Set case sensitivity
        if not case_sensitive:
            rg = rg.ignore_case()
        else:
            rg = rg.case_sensitive()

        # Execute the search
        result = rg.run()

        # Check if there are any matches
        if result.as_string:
            return result.as_string
        else:
            return f"No matches found for '{search_string}' in file '{path}'."

    except (RipGrepNotFound, FileNotFoundError, OSError):
        # Fallback to manual implementation if ripgrep is not available or other OS errors
        matches = []
        line_num = 0
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line_num += 1
                    if (case_sensitive and search_string in line) or (not case_sensitive and search_string.lower() in line.lower()):
                        matches.append(f"{line_num}:{line.rstrip()}")
                        if len(matches) >= max_lines:
                            break
        except UnicodeDecodeError:
            return f"Error: '{path}' is a binary file. Cannot perform grep operation."
        except FileNotFoundError:
            return f"Error: File '{path}' not found."

        if matches:
            return "\n".join(matches)
        else:
            return f"No matches found for '{search_string}' in file '{path}'."
    except Exception as e:
        return f"Error searching file '{path}': {str(e)}"

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
    If using python to write a file, be sure to clear the file out before every run.
    Libraries available:
        Python standard library
        beautifulsoup4

    Binaries available:
        curl
        wget
        ocr /path/to/image.jpg -- Performs OCR on the image and returns extracted text. Use this instead of PIL or pytesseract for image OCR.
        ocr https://example.com/screenshot.png

    Args:  
        path: The path where the Python script will be created
            content: The Python code to write into the script
        content: The content to write into the file

    Returns:
        Confirmation message
    """
    import os
    try:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

        return f"Python script '{path}' created with {len(content)} characters."
    except Exception as e:
        return f"Error creating python script '{path}': {str(e)}"

# Export tools as a list for easy import
FILE_TOOLS = [
    read_file,
    grep_file,
    create_file_with_content,
    append_to_file,
    create_python_script
]
