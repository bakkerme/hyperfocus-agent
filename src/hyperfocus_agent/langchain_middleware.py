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
from collections.abc import Callable
from urllib.parse import urlparse
import requests

from langchain_openai import ChatOpenAI
from langchain.agents.middleware import (
    wrap_model_call,
    before_model,
    wrap_tool_call,
    ModelRequest,
    ModelResponse,
)

from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage, HumanMessage
from langgraph.types import Command
import json

from .langchain_state import HyperfocusState


# Global model references (will be initialized in create_agent)
local_model: ChatOpenAI | None = None
remote_model: ChatOpenAI | None = None
multimodal_model: ChatOpenAI | None = None
router_threshold: int = 10000


def initialize_models(local: ChatOpenAI, remote: ChatOpenAI, multimodal: ChatOpenAI | None = None, threshold: int = 10000):
    """Initialize the global model references for middleware to use."""
    global local_model, remote_model, multimodal_model, router_threshold
    local_model = local
    remote_model = remote
    multimodal_model = multimodal
    router_threshold = threshold
    print(f"✓ Models initialized for middleware")


@before_model
def strip_processed_images(state: HyperfocusState, runtime) -> dict | None:
    """Remove images from messages after their first iteration.

    This middleware ensures that images only stay in context for the iteration
    they were added, allowing the multimodal model to process them once, then
    switching back to the more powerful non-multimodal model for subsequent turns.

    The strategy:
    1. Track which messages have images
    2. After an AI response to an image, replace the image content with a text stub
    3. This keeps conversation flow intact while removing heavy multimodal content
    """
    messages = state.get("messages", [])

    if not messages:
        return None

    # Find the last AI message - if it exists, we've processed any images before it
    last_ai_index = -1
    for i in range(len(messages) - 1, -1, -1):
        if hasattr(messages[i], 'type') and messages[i].type == "ai":
            last_ai_index = i
            break

    # If there's no AI message yet, this is the first turn - don't strip anything
    if last_ai_index == -1:
        return None

    # Strip images from messages BEFORE the last AI message
    # (The AI has already seen and processed them)
    modified_messages = []
    images_stripped = False

    for i, message in enumerate(messages):
        if i < last_ai_index and _message_has_image_content(message):
            # Replace with text-only version
            modified_message = _strip_image_from_message(message)
            modified_messages.append(modified_message)
            images_stripped = True
            print(f"→ [Image Cleanup] Stripped image from message at index {i}")
        else:
            modified_messages.append(message)

    # Return state update only if we modified anything
    if images_stripped:
        return {"messages": modified_messages}

    return None


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
    threshold = router_threshold

    if total_length > threshold and remote_model is not None:
        print(f"→ [LLM Router] Using REMOTE LLM (length: {total_length} > {threshold})")
        request.model = remote_model
    else:
        print(f"→ [LLM Router] Using LOCAL LLM (length: {total_length} ≤ {threshold})")
        request.model = local_model if local_model is not None else remote_model

    return handler(request)


# Helper functions

def _message_has_image_content(message) -> bool:
    """Check if a single message contains image content."""
    if not hasattr(message, 'content'):
        return False

    content = message.content

    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                item_type = item.get("type", "")
                if item_type in ("image", "image_url"):
                    return True
    return False


def _strip_image_from_message(message):
    """Remove image content from a message, replacing it with a text stub.

    Returns a new message with images replaced by text placeholders.
    """
    if not hasattr(message, 'content'):
        return message

    content = message.content

    # If content is not a list, nothing to strip
    if not isinstance(content, list):
        return message

    # Filter out image content blocks, keep text
    new_content = []
    for item in content:
        if isinstance(item, dict):
            item_type = item.get("type", "")
            if item_type in ("image", "image_url"):
                # Replace with text stub
                new_content.append({
                    "type": "text",
                    "text": "[Image was analyzed in previous turn]"
                })
            else:
                new_content.append(item)
        else:
            new_content.append(item)

    # Create a new message with the modified content
    # We need to preserve the message type and other attributes
    message_class = type(message)
    new_message = message_class(content=new_content)

    # Copy over other important attributes if they exist
    if hasattr(message, 'id'):
        new_message.id = message.id
    if hasattr(message, 'name'):
        new_message.name = message.name

    return new_message


def _has_image_content(messages: list) -> bool:
    """Check if any message contains image content.

    Supports both:
    - LangChain standard: content=[{"type": "image", ...}]
    - OpenAI native: content=[{"type": "image_url", ...}]
    """
    for message in messages:
        # Check if message has content attribute
        if not hasattr(message, 'content'):
            continue

        content = message.content

        # If content is a list, check each item
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    item_type = item.get("type", "")
                    if item_type in ("image", "image_url"):
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


@wrap_tool_call
def log_tool_execution(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command]
) -> ToolMessage | Command:
    """Log tool calls with their inputs for debugging and observability.
    
    This middleware logs:
    - Tool name
    - Tool arguments (formatted JSON)
    - Result (truncated if large)
    """
    tool = request.tool
    if tool is None:
        return ToolMessage(content="No tool found in request.")

    tool_name = tool.name
    tool_input = request.tool_call["args"]
    
    # Format the input nicely
    try:
        input_str = json.dumps(tool_input, indent=2)
    except Exception:
        input_str = str(tool_input)
    
    print(f"\n→ [Tool Call] {tool_name}")
    print(f"  Input: {input_str}")
   
    return handler(request)