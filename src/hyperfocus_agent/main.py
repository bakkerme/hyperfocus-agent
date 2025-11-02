from openai import OpenAI
from .directory_ops import DIRECTORY_TOOLS
from .file_ops import FILE_TOOLS
from .utils import UTILITY_TOOLS
from .tool_router import execute_tool_call, execute_tool_calls


def main():
    # Connect to LM Studio
    client = OpenAI(base_url="http://100.89.244.102:1234/v1", api_key="lm-studio")

    # Combine all tool definitions
    tools = UTILITY_TOOLS + DIRECTORY_TOOLS + FILE_TOOLS

    # Ask the AI to use our function
    response = client.chat.completions.create(
        model="qwen/qwen3-30b-a3b-2507",
        messages=[{"role": "user", "content": "Can you say hello to Bob the Builder?"}],
        tools=tools
    )

    # Check if the AI requested any tool calls
    if response.choices[0].message.tool_calls:
        # Execute all tool calls securely using the router
        results = execute_tool_calls(response.choices[0].message.tool_calls)
        
        # Print results
        for result in results:
            if result["success"]:
                print(f"✓ {result['function_name']}: {result['result']}")
            else:
                print(f"✗ {result['function_name']}: {result['error']}")

if __name__ == "__main__":
    main()