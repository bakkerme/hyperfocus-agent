import subprocess
from .types import ChatCompletionToolParam

def execute_shell_command(command: str) -> str:
    """
    Executes a shell command on the local system and returns the output.
    """
    try:
        result = subprocess.run(
            command, shell=True, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Error executing command: {e.stderr.strip()}"

SHELL_TOOLS: list[ChatCompletionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "execute_shell_command",
            "description": "Executes a shell command on the local system",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute"
                    }
                },
                "required": ["command"]
            }
        }
    }
] 