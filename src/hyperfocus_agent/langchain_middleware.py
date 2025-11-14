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