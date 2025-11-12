"""LangChain 1.0 agent setup and creation.

This module contains the main agent factory using LangChain 1.0's create_agent API.
Migrated from LangGraph's deprecated create_react_agent to the new langchain.agents
API with middleware support.
"""
import os
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver

from .agent import get_base_prompt
from .langchain_state import HyperfocusState, HyperfocusContext
from .langchain_middleware import (
    initialize_models,
    dynamic_model_selection,
    inject_images_from_load_image,
)


def create_hyperfocus_agent():
    """Create the Hyperfocus LangChain 1.0 agent with all middleware and tools.

    This uses LangChain 1.0's create_agent API which provides:
    - Built-in tool execution loop
    - Middleware system for customization
    - Dynamic model selection
    - Message history management with checkpointing

    Returns:
        Configured LangChain agent ready to use
    """
    # Read environment variables
    local_base_url = os.getenv("LOCAL_OPENAI_BASE_URL")
    local_api_key = os.getenv("LOCAL_OPENAI_API_KEY")
    local_model_name = os.getenv("LOCAL_OPENAI_MODEL")

    remote_base_url = os.getenv("REMOTE_OPENAI_BASE_URL")
    remote_api_key = os.getenv("REMOTE_OPENAI_API_KEY")
    remote_model_name = os.getenv("REMOTE_OPENAI_MODEL")

    multimodal_base_url = os.getenv("MULTIMODAL_OPENAI_BASE_URL")
    multimodal_api_key = os.getenv("MULTIMODAL_OPENAI_API_KEY")
    multimodal_model_name = os.getenv("MULTIMODAL_OPENAI_MODEL")

    # Validate required environment variables
    if not all([local_base_url, local_api_key, local_model_name]):
        raise ValueError(
            "LOCAL_OPENAI_BASE_URL, LOCAL_OPENAI_API_KEY, and LOCAL_OPENAI_MODEL "
            "environment variables must be set."
        )

    if not all([remote_base_url, remote_api_key, remote_model_name]):
        raise ValueError(
            "REMOTE_OPENAI_BASE_URL, REMOTE_OPENAI_API_KEY, and REMOTE_OPENAI_MODEL "
            "environment variables must be set."
        )

    print(f"Initializing LangChain 1.0 agent...")
    print(f"  Local: {local_base_url} / {local_model_name}")
    print(f"  Remote: {remote_base_url} / {remote_model_name}")

    # Initialize models using LangChain's ChatOpenAI
    # Set reasonable max_tokens to avoid exceeding context limits
    local_model = ChatOpenAI(
        model=local_model_name,
        api_key=local_api_key,
        base_url=local_base_url,
        temperature=0,
        max_tokens=4096
    )

    remote_model = ChatOpenAI(
        model=remote_model_name,
        api_key=remote_api_key,
        base_url=remote_base_url,
        temperature=0,
        max_tokens=4096
    )

    # Optional multimodal model
    multimodal_model = None
    if multimodal_base_url and multimodal_api_key and multimodal_model_name:
        print(f"  Multimodal: {multimodal_base_url} / {multimodal_model_name}")
        multimodal_model = ChatOpenAI(
            model=multimodal_model_name,
            api_key=multimodal_api_key,
            base_url=multimodal_base_url,
            temperature=0,
            max_tokens=2048
        )

    # Initialize global model references for middleware
    initialize_models(local_model, remote_model, multimodal_model)

    # Import migrated tools
    from .langchain_tools import ALL_TOOLS

    print(f"✓ Loaded {len(ALL_TOOLS)} tools")

    # Get system prompt from agent module
    system_prompt = get_base_prompt()

    # Create agent using LangChain 1.0 API
    # Middleware order matters:
    # 1. inject_images_from_load_image - Intercepts load_image and injects images
    # 2. dynamic_model_selection - Routes to multimodal LLM when images detected
    agent = create_agent(
        model=local_model,  # Default model (will be overridden by middleware)
        tools=ALL_TOOLS,
        system_prompt=system_prompt,
        state_schema=HyperfocusState,
        context_schema=HyperfocusContext,
        middleware=[inject_images_from_load_image, dynamic_model_selection],
        checkpointer=MemorySaver(),
    )

    print("✓ LangChain 1.0 agent initialized successfully")
    print("✓ Migrated to create_agent with middleware-based model routing")
    print("✓ Multimodal image injection enabled via @wrap_tool_call middleware")
    return agent


def get_agent_config(thread_id: str = "cli-session") -> dict:
    """Get the configuration for agent invocation.

    Args:
        thread_id: Unique identifier for this conversation thread

    Returns:
        Configuration dict for agent.invoke() or agent.stream()
    """
    # LangChain 1.0 uses the same config structure
    return {
        "configurable": {
            "thread_id": thread_id
        }
    }
