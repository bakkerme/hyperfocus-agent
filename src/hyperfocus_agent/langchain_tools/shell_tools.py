"""Shell command execution migrated to LangChain @tool decorator pattern.

This module replaces shell_ops.py with LangChain-compatible tools.
"""
import subprocess
from langchain_core.tools import tool


@tool
def execute_shell_command(command: str) -> str:
    """Execute a shell command on the local system and return the output.

    SECURITY WARNING: This tool executes arbitrary shell commands with full
    user permissions. Only use with trusted input.

    Avoid installing new packages or running destructive commands without explicit
    user consent.

    Args:
        command: The shell command to execute

    Returns:
        The stdout of the command, or error message if execution failed
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30  # 30 second timeout to prevent hanging
        )

        output = result.stdout.strip()

        if not output:
            return f"Command executed successfully (no output)."

        return output

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after 30 seconds."

    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip()
        return f"Error executing command (exit code {e.returncode}):\n{stderr}"

    except Exception as e:
        return f"Unexpected error: {str(e)}"


# Export tools as a list for easy import
SHELL_TOOLS = [
    execute_shell_command
]
