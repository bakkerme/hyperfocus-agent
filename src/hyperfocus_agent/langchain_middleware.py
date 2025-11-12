"""Middleware for LangChain 1.0 agent.

This module contains middleware using the new LangChain 1.0 patterns:
1. Dynamic model selection via @wrap_model_call
2. Image injection via @wrap_tool_call
3. Conditional context via @before_model (future)
4. Iteration tracking (future)
"""
import os
import base64
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
import requests

from langchain_openai import ChatOpenAI
from langchain.agents.middleware import (
    wrap_model_call,
    wrap_tool_call,
    ModelRequest,
    ModelResponse,
)
from langchain_core.messages import ToolMessage, HumanMessage
from langgraph.types import Command

from .langchain_state import HyperfocusState


# Global model references (will be initialized in create_agent)
local_model: ChatOpenAI | None = None
remote_model: ChatOpenAI | None = None
multimodal_model: ChatOpenAI | None = None


def initialize_models(local: ChatOpenAI, remote: ChatOpenAI, multimodal: ChatOpenAI | None = None):
    """Initialize the global model references for middleware to use."""
    global local_model, remote_model, multimodal_model
    local_model = local
    remote_model = remote
    multimodal_model = multimodal
    print(f"✓ Models initialized for middleware")


@wrap_model_call
def dynamic_model_selection(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse]
) -> ModelResponse:
    """Select which LLM to use based on context size and content.

    This implements the core logic from llm_router.py using LangChain 1.0's
    middleware pattern.
    """
    state = request.state
    messages = state.get("messages", [])

    # Check for multimodal content
    if _has_image_content(messages) and multimodal_model is not None:
        print("→ [LLM Router] Using MULTIMODAL LLM")
        request.model = multimodal_model
        return handler(request)

    # Calculate message length
    total_length = _calculate_message_length(messages)
    threshold = int(os.getenv("LLM_ROUTER_THRESHOLD", "10000"))

    if total_length > threshold and remote_model is not None:
        print(f"→ [LLM Router] Using REMOTE LLM (length: {total_length} > {threshold})")
        request.model = remote_model
    else:
        print(f"→ [LLM Router] Using LOCAL LLM (length: {total_length} ≤ {threshold})")
        request.model = local_model if local_model is not None else remote_model

    return handler(request)


# Helper functions

def _has_image_content(messages: list) -> bool:
    """Check if any message contains image content."""
    for message in messages:
        if hasattr(message, 'content') and isinstance(message.content, list):
            for item in message.content:
                if isinstance(item, dict) and item.get("type") == "image_url":
                    return True
    return False


def _calculate_message_length(messages: list) -> int:
    """Calculate the total character count of all message content."""
    total_length = 0
    for message in messages:
        if hasattr(message, 'content'):
            content = message.content
            if isinstance(content, str):
                total_length += len(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        total_length += len(item.get("text", ""))
    return total_length


# Image Injection Middleware

@wrap_tool_call
def inject_images_from_load_image(request, handler) -> ToolMessage | Command:
    """Intercept load_image tool calls and inject images into conversation.

    This middleware solves the multimodal problem: when load_image is called,
    we need to inject the actual image content into the message history so
    the multimodal LLM can analyze it.

    LangChain 1.0's @wrap_tool_call allows us to:
    1. Execute the tool normally
    2. Return a Command that adds additional messages (the image!)
    """
    tool_call = request.tool_call
    tool_name = tool_call.get("name", "")

    # Only intercept load_image calls
    if tool_name != "load_image":
        # For all other tools, execute normally
        return handler(request)

    # Get the file path argument
    file_path = tool_call.get("args", {}).get("file_path", "")

    if not file_path:
        # If no file path, execute tool normally
        return handler(request)

    print(f"→ [Image Injection] Intercepting load_image call for: {file_path}")

    # Execute the tool normally first to validate the image
    tool_result = handler(request)

    # Check if tool execution failed
    if isinstance(tool_result, ToolMessage) and "Error" in tool_result.content:
        # If tool failed, just return the error
        return tool_result

    # Tool succeeded - now load and inject the image
    try:
        image_data, mime_type = _load_and_encode_image(file_path)

        print(f"→ [Image Injection] Loaded image: {mime_type}, {len(image_data)} chars base64")
        print(f"→ [Image Injection] Injecting image into conversation for multimodal analysis")

        # Return a Command that adds both:
        # 1. The tool result message (confirming image loaded)
        # 2. A HumanMessage with the actual image content
        return Command(
            update={
                "messages": [
                    tool_result,  # Keep the original tool result
                    HumanMessage(
                        content=[
                            {"type": "text", "text": "Please analyze this image:"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_data}"
                                }
                            }
                        ]
                    )
                ]
            }
        )

    except Exception as e:
        print(f"→ [Image Injection] Failed to inject image: {e}")
        # If injection fails, return the original tool result
        return tool_result


def _load_and_encode_image(file_path: str) -> tuple[str, str]:
    """Load an image and return (base64_data, mime_type).

    Supports both local files and remote URLs.
    """
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }

    # Check if URL or local file
    parsed = urlparse(file_path)
    is_remote = parsed.scheme in ('http', 'https')

    if is_remote:
        # Handle remote URL
        response = requests.get(file_path, timeout=30)
        response.raise_for_status()
        image_data = response.content

        # Determine MIME type
        content_type = response.headers.get('content-type', '').lower()
        if 'image/' in content_type:
            mime_type = content_type.split(';')[0].strip()
        else:
            extension = Path(parsed.path).suffix.lower()
            mime_type = mime_types.get(extension, 'image/jpeg')

        base64_data = base64.b64encode(image_data).decode('utf-8')

    else:
        # Handle local file
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {file_path}")

        extension = path.suffix.lower()
        mime_type = mime_types.get(extension, 'image/jpeg')

        # Read and encode image
        with open(file_path, 'rb') as f:
            image_data = f.read()

        base64_data = base64.b64encode(image_data).decode('utf-8')

    return base64_data, mime_type
