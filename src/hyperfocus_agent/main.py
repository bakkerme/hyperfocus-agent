import argparse
import os
from typing import List, cast
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from .directory_ops import DIRECTORY_TOOLS
from .file_ops import FILE_TOOLS
from .utils import UTILITY_TOOLS
from .shell_ops import SHELL_TOOLS
from .web_ops import WEB_TOOLS
from .tool_router import execute_tool_calls
from .agent import get_base_prompt


def parse_args():
    """Parse CLI arguments for the message to send to the model."""
    parser = argparse.ArgumentParser(description="Send a user message to the LM Studio backend.")
    parser.add_argument("message", nargs="+", help="User message content for the model")
    return parser.parse_args()


def main():
    args = parse_args()
    user_message = " ".join(args.message)

    # Connect to LM Studio (read from environment variables with defaults)
    base_url = os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")

    if not base_url or not api_key or not model or base_url.strip() == "" or api_key.strip() == "" or model.strip() == "":
        print("Error: OPENAI_BASE_URL, OPENAI_API_KEY, and OPENAI_MODEL environment variables must be set.")
        return

    print(f"Using base URL: {base_url}")
    print(f"Using model: {model}")

    client = OpenAI(base_url=base_url, api_key=api_key)

    # Combine all tool definitions
    tools = UTILITY_TOOLS + DIRECTORY_TOOLS + FILE_TOOLS + SHELL_TOOLS + WEB_TOOLS

    # Maintain the full conversation so the model can react to executed tools
    messages: list[ChatCompletionMessageParam] = [
        cast(ChatCompletionMessageParam, {"role": "system", "content": get_base_prompt()}),
        cast(ChatCompletionMessageParam, {"role": "user", "content": user_message})
    ]
    max_tool_iterations = int(os.getenv("LM_TOOL_CALL_ITERATIONS", "50"))
    iteration = 0

    while True:
        print(f"\n Sending messages to model {messages}")
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools
        )

        assistant_message = response.choices[0].message
        assistant_message_dict = cast(
            ChatCompletionMessageParam,
            assistant_message.model_dump()
        )

        # Ensure the content field is always a string for the next round trip
        if assistant_message_dict.get("content") is None:
            assistant_message_dict["content"] = ""

        messages.append(assistant_message_dict)

        assistant_content = assistant_message_dict.get("content")
        if assistant_content:
            print(assistant_content)

        tool_calls = assistant_message.tool_calls or []
        if not tool_calls:
            break

        if iteration >= max_tool_iterations:
            print("✗ tool_call_loop: exceeded maximum tool iterations")
            break

        results = execute_tool_calls(tool_calls)

        for result in results:
            if result["success"]:
                tool_content = str(result["result"])
                # print(f"✓ {result['function_name']}: {tool_content}")
                print(f"✓ {result['function_name']}: {result['arguments']}")
            else:
                tool_content = f"Error: {result['error']}"
                # print(f"✗ {result['function_name']}: {result['error']}")
                print(f"✗ {result['function_name']}: args: {result['arguments']}, error: {result['error']}")

            tool_message = cast(
                ChatCompletionMessageParam,
                {
                    "role": "tool",
                    "tool_call_id": result["tool_call_id"],
                    "content": tool_content,
                },
            )
            messages.append(tool_message)

        iteration += 1

if __name__ == "__main__":
    main()