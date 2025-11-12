"""LangChain agent setup and creation.

This module contains the main agent factory that replaces the manual
orchestration loop in the original main.py.

Phase 1: Basic structure with placeholder tools
Phase 2+: Full tool migration and middleware implementation
"""
import os
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from .agent import get_base_prompt
from .langchain_state import HyperfocusState
from .langchain_middleware import initialize_models, select_llm_model


def create_hyperfocus_agent():
    """Create the Hyperfocus LangChain agent with all middleware and tools.

    This replaces the manual orchestration loop in the original main.py.
    The agent handles:
    - Tool execution
    - Message history management
    - Context stubbing via middleware (Phase 2)
    - LLM routing via middleware
    - Iteration tracking via middleware (Phase 2)

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

    print(f"Initializing LangChain agent...")
    print(f"  Local: {local_base_url} / {local_model_name}")
    print(f"  Remote: {remote_base_url} / {remote_model_name}")

    # Initialize models using LangChain's ChatOpenAI
    local_model = ChatOpenAI(
        model=local_model_name,
        api_key=local_api_key,
        base_url=local_base_url,
        temperature=0
    )

    remote_model = ChatOpenAI(
        model=remote_model_name,
        api_key=remote_api_key,
        base_url=remote_base_url,
        temperature=0
    )

    # Optional multimodal model
    multimodal_model = None
    if multimodal_base_url and multimodal_api_key and multimodal_model_name:
        print(f"  Multimodal: {multimodal_base_url} / {multimodal_model_name}")
        multimodal_model = ChatOpenAI(
            model=multimodal_model_name,
            api_key=multimodal_api_key,
            base_url=multimodal_base_url,
            temperature=0
        )

    # Initialize global model references for middleware
    initialize_models(local_model, remote_model, multimodal_model)

    # Phase 2: Import migrated tools
    from .langchain_tools import ALL_TOOLS

    print(f"✓ Loaded {len(ALL_TOOLS)} tools")

    # Create the agent using LangGraph's prebuilt create_react_agent
    # This handles the tool calling loop automatically
    agent = create_react_agent(
        model=local_model,  # Default model (middleware will swap as needed)
        tools=ALL_TOOLS,
        checkpointer=MemorySaver(),  # In-memory state management
        state_schema=HyperfocusState  # Our custom state
    )

    print("✓ LangChain agent initialized successfully")
    print("✓ Phase 2 complete - agent ready with migrated tools")
    return agent


def get_agent_config(thread_id: str = "cli-session") -> dict:
    """Get the configuration for agent invocation.

    Args:
        thread_id: Unique identifier for this conversation thread

    Returns:
        Configuration dict for agent.invoke() or agent.stream()
    """
    return {
        "configurable": {
            "thread_id": thread_id
        }
    }
