import argparse
import os
from typing import List, cast
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from .directory_ops import DIRECTORY_TOOLS
from .file_ops import FILE_TOOLS
from .shell_ops import SHELL_TOOLS
from .web_ops import WEB_TOOLS
from .image_ops import IMAGE_TOOLS
from .task_ops import TASK_TOOLS
from .tool_router import execute_tool_calls
from .agent import get_base_prompt, get_first_step_prompt
from .llm_router import LLMRouter
from .task_executor import initialize_task_executor


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

    # Optional multi-modal client for vision capabilities
    multimodal_url = os.getenv("MULTIMODAL_OPENAI_BASE_URL")
    multimodal_api_key = os.getenv("MULTIMODAL_OPENAI_API_KEY")
    multimodal_model = os.getenv("MULTIMODAL_OPENAI_MODEL")

    multimodal_client = None
    if multimodal_url and multimodal_api_key and multimodal_model:
        multimodal_client = OpenAI(base_url=multimodal_url, api_key=multimodal_api_key)
        print(f"Using multimodal base URL: {multimodal_url}")
        print(f"Using multimodal model: {multimodal_model}")

    # Initialize the LLM router
    llm_router = LLMRouter(
        local_client=local_client,
        remote_client=remote_client,
        local_model=local_model,
        remote_model=remote_model,
        multimodal_client=multimodal_client,
        multimodal_model=multimodal_model
    )

    # Initialize the task executor with the LLM router
    initialize_task_executor(llm_router)

    # Combine all tool definitions
    tools = DIRECTORY_TOOLS + FILE_TOOLS + SHELL_TOOLS + WEB_TOOLS + IMAGE_TOOLS + TASK_TOOLS

    # Maintain the full conversation so the model can react to executed tools
    messages: list[ChatCompletionMessageParam] = [
        cast(ChatCompletionMessageParam, {"role": "system", "content": get_base_prompt()}),
        cast(ChatCompletionMessageParam, {"role": "user", "content": user_message}),
        cast(ChatCompletionMessageParam, {"role": "system", "content": get_first_step_prompt()}),
    ]
    max_tool_iterations = int(os.getenv("LM_TOOL_CALL_ITERATIONS", "500"))
    iteration = 0
    # Track if we had an image in the previous iteration
    had_image_last_iteration = False

    should_stream = True

    while True:
        # print(f"\n Sending messages to model {messages}")
        response = llm_router.complete(
            messages=messages,
            tools=tools,
            stream=should_stream
        )


        assistant_message = response.choices[0].message
        assistant_message_dict = cast(
            ChatCompletionMessageParam,
            assistant_message.model_dump()
        )

        if not should_stream:
            print(assistant_message.content)

        # Ensure the content field is always a string for the next round trip
        if assistant_message_dict.get("content") is None:
            assistant_message_dict["content"] = ""

        messages.append(assistant_message_dict)

        tool_calls = assistant_message.tool_calls or []
        if not tool_calls:
            print("✓ tool_call_loop: no more tool calls, finishing execution")
            break

        if iteration >= max_tool_iterations:
            print("✗ tool_call_loop: exceeded maximum tool iterations")
            break

        results = execute_tool_calls(tool_calls)

        # Check if any of the results contain image data
        has_image_this_iteration = False

        # Store image data to be added after all tool messages
        image_data_to_add = None

        for result in results:
            if result["success"]:
                result_data = result["result"]

                # Check if this is an image load result
                if isinstance(result_data, dict) and result_data.get("use_multimodal"):
                    has_image_this_iteration = True
                    print(f"✓ {result['function_name']}: {result_data.get('message', 'Image loaded')}")

                    # Store image data to add as a user message after tool messages
                    image_data_to_add = result_data

                    # Add a simple text tool response first
                    tool_message = cast(
                        ChatCompletionMessageParam,
                        {
                            "role": "tool",
                            "tool_call_id": result["tool_call_id"],
                            "content": result_data.get("message", "Image loaded successfully"),
                        },
                    )
                    messages.append(tool_message)
                else:
                    tool_content = str(result_data)
                    print(f"✓ {result['function_name']}: {result['arguments']}")
                    print(tool_content)

                    tool_message = cast(
                        ChatCompletionMessageParam,
                        {
                            "role": "tool",
                            "tool_call_id": result["tool_call_id"],
                            "content": tool_content,
                        },
                    )
                    messages.append(tool_message)
            else:
                tool_content = f"Error: {result['error']}"
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

        # If we have image data, add it as a user message with vision content
        # This must come AFTER all tool messages
        if image_data_to_add:
            user_image_message = cast(
                ChatCompletionMessageParam,
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{image_data_to_add['mime_type']};base64,{image_data_to_add['base64_data']}"
                            }
                        }
                    ]
                }
            )
            messages.append(user_image_message)

        # If we had an image last iteration but not this iteration,
        # we need to remove image content from messages to avoid using multimodal model
        if had_image_last_iteration and not has_image_this_iteration:
            # Create a cleaned version of messages without image content
            cleaned_messages = []
            for msg in messages:
                content = msg.get("content")
                if isinstance(content, list):
                    # Extract only text content, skip images
                    text_parts = [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"]
                    cleaned_msg = dict(msg)
                    cleaned_msg["content"] = " ".join(text_parts) if text_parts else ""
                    cleaned_messages.append(cast(ChatCompletionMessageParam, cleaned_msg))
                else:
                    cleaned_messages.append(msg)
            messages = cleaned_messages

        had_image_last_iteration = has_image_this_iteration
        iteration += 1

if __name__ == "__main__":
    main()