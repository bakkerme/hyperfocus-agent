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
from .agent import get_base_prompt, get_first_step_prompt
from .llm_router import LLMRouter


def parse_args():
    """Parse CLI arguments for the message to send to the model."""
    parser = argparse.ArgumentParser(description="Send a user message to the LM Studio backend.")
    parser.add_argument("message", nargs="+", help="User message content for the model")
    return parser.parse_args()


def main():
    args = parse_args()
    user_message = " ".join(args.message)

    # Connect to LLM (read from environment variables with defaults)
    local_base_url = os.getenv("LOCAL_OPENAI_BASE_URL")
    local_api_key = os.getenv("LOCAL_OPENAI_API_KEY")
    local_model = os.getenv("LOCAL_OPENAI_MODEL")

    remote_url = os.getenv("REMOTE_OPENAI_BASE_URL")
    remote_api_key = os.getenv("REMOTE_OPENAI_API_KEY")
    remote_model = os.getenv("REMOTE_OPENAI_MODEL")

    if not local_base_url or not local_api_key or not local_model or local_base_url.strip() == "" or local_api_key.strip() == "" or local_model.strip() == "":
        print("Error: OPENAI_BASE_URL, OPENAI_API_KEY, and OPENAI_MODEL environment variables must be set.")
        return
    
    if not remote_url or not remote_api_key or not remote_model or remote_url.strip() == "" or remote_api_key.strip() == "" or remote_model.strip() == "":
        print("Error: REMOTE_OPENAI_BASE_URL, REMOTE_OPENAI_API_KEY, and REMOTE_OPENAI_MODEL environment variables must be set.")
        return

    print(f"Using local base URL: {local_base_url}")
    print(f"Using local model: {local_model}")

    print(f"Using remote base URL: {remote_url}")
    print(f"Using remote model: {remote_model}")

    local_client = OpenAI(base_url=local_base_url, api_key=local_api_key)
    remote_client = OpenAI(base_url=remote_url, api_key=remote_api_key)
    
    # Initialize the LLM router
    llm_router = LLMRouter(
        local_client=local_client,
        remote_client=remote_client,
        local_model=local_model,
        remote_model=remote_model
    )

    # Combine all tool definitions
    tools = UTILITY_TOOLS + DIRECTORY_TOOLS + FILE_TOOLS + SHELL_TOOLS + WEB_TOOLS

    # Maintain the full conversation so the model can react to executed tools
    messages: list[ChatCompletionMessageParam] = [
        cast(ChatCompletionMessageParam, {"role": "system", "content": get_base_prompt()}),
        cast(ChatCompletionMessageParam, {"role": "user", "content": user_message}),
        cast(ChatCompletionMessageParam, {"role": "system", "content": get_first_step_prompt()}),
    ]
    max_tool_iterations = int(os.getenv("LM_TOOL_CALL_ITERATIONS", "50"))
    iteration = 0

    while True:
        # print(f"\n Sending messages to model {messages}")
        response = llm_router.complete(
            messages=messages,
            tools=tools,
            stream=True
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

        # Note: Content is already printed during streaming in llm_router._handle_streaming_response
        # No need to print it again here

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