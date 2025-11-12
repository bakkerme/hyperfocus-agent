"""Middleware functions for LangChain agent.

This module contains placeholder middleware that will be refined in Phase 2.
For Phase 1, we're establishing the structure and ensuring imports work.

The full middleware implementation will handle:
1. Conditional context (replaces context_builder.py)
2. LLM routing (replaces llm_router.py)
3. Iteration tracking
"""
import os
from typing import Any
from langchain_openai import ChatOpenAI

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


# Note: Full middleware implementation will be added in Phase 2
# For now, these are placeholders to establish the structure

def conditional_context_filter(state: HyperfocusState) -> HyperfocusState:
    """Placeholder for context filtering middleware.

    Will implement iteration-based message stubbing in Phase 2.
    """
    # TODO: Implement in Phase 2
    return state


def select_llm_model(state: HyperfocusState) -> ChatOpenAI:
    """Select which LLM to use based on context size and content.

    This implements the core logic from llm_router.py.
    """
    messages = state.get("messages", [])

    # Check for multimodal content
    if _has_image_content(messages) and multimodal_model is not None:
        print("→ [LLM Router] Using MULTIMODAL LLM")
        return multimodal_model

    # Calculate message length
    total_length = _calculate_message_length(messages)
    threshold = int(os.getenv("LLM_ROUTER_THRESHOLD", "10000"))

    if total_length > threshold and remote_model is not None:
        print(f"→ [LLM Router] Using REMOTE LLM (length: {total_length} > {threshold})")
        return remote_model
    else:
        print(f"→ [LLM Router] Using LOCAL LLM (length: {total_length} ≤ {threshold})")
        return local_model if local_model is not None else remote_model


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
