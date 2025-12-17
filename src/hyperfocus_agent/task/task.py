from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from ..utils.image_utils import load_image_as_base64
from ..model_config import ModelConfig

# Import tools that sub-agents can optionally use
from ..langchain_tools.directory_tools import DIRECTORY_TOOLS
from ..langchain_tools.file_tools import FILE_TOOLS

# Core task execution logic (runtime-free)
def execute_task(
    prompt: str,
    data_text: str | None = None,
    image_path: str | None = None,
    enable_tools: bool = False,
) -> str:
    """Execute a task using a sub-agent with flexible input types.
    
    This is the internal implementation that can be called directly by other tools
    without going through the LangChain @tool decorator and Command system.
    
    Args:
        prompt: Task instructions for what to do with the data
        data_text: Optional direct text input
        image_path: Optional path to image file for vision analysis
        enable_tools: Whether to give sub-agent access to file/directory tools
        
    Returns:
        String containing the sub-agent's response
        
    Raises:
        ValueError: If inputs are invalid or task execution fails
        
    Examples:
        result = execute_task(
            "Extract key points",
            data_text="Long article..."
        )
    """
    # 1. VALIDATE INPUTS
    if not any([data_text, image_path]):
        raise ValueError("Must provide at least one of: data_text or image_path")
    
    # 2. BUILD TASK MESSAGES
    messages = _build_task_messages(
        prompt=prompt,
        data_text=data_text,
        image_path=image_path,
    )
    
    # 3. CREATE APPROPRIATE SUB-AGENT
    has_image = image_path is not None
    sub_agent = _create_sub_agent(has_image=has_image, enable_tools=enable_tools)
    
    # 4. EXECUTE TASK
    result = sub_agent.invoke(
        {"messages": messages},  # type: ignore
        config={"recursion_limit": 10}
    )
    
    # Extract response
    output_messages = result.get("messages", [])
    if output_messages:
        return output_messages[-1].content
    else:
        raise ValueError("No response from sub-agent")

def _build_task_messages(
    prompt: str,
    data_text: str | None,
    image_path: str | None,
) -> list[HumanMessage]:
    """Build message list for sub-agent based on input types.
    
    Supports text-only, multimodal, and combined inputs.
    """
    
    # 1. Build prompt text with data
    data_to_process = data_text or ""

    messages = [HumanMessage(content=prompt)]
    if data_to_process:
        messages.append(HumanMessage(content=data_to_process))

    # 2. Add image if provided
    if image_path:
        image_data = load_image_as_base64(image_path)
        messages.append(HumanMessage(content={
            "type": "image_url",
            "image_url": {
                "url": f"data:{image_data['mime_type']};base64,{image_data['base64_data']}"
            }
        }))
    
    return messages

def _create_sub_agent(
    has_image: bool = False,
    enable_tools: bool = False,
):
    """Create sub-agent with appropriate model and tools.
    
    Args:
        has_image: Whether task includes image (use multimodal model)
        enable_tools: Whether to give sub-agent access to tools
    """
    config = ModelConfig.from_environment()
    
    # Select model based on input type
    if has_image and config.multimodal:
        # Create non-streaming multimodal model
        sub_llm = ChatOpenAI(
            model=config.multimodal.model_name,  # type: ignore
            api_key=config.multimodal.openai_api_key,  # type: ignore
            base_url=config.multimodal.openai_api_base,  # type: ignore
            temperature=0,
            streaming=False,
        )
        model_name = "multimodal"
    else:
        sub_llm = config.create_non_streaming_local()
        model_name = "local"
    
    # Select tools
    tools = []
    if enable_tools:
        tools = [*DIRECTORY_TOOLS, *FILE_TOOLS]
    
    # Build system prompt
    system_prompt = _get_task_system_prompt(has_image, enable_tools)
    
    print(f"→ [Sub-Agent] Using {model_name.upper()} model, tools={'enabled' if enable_tools else 'disabled'}")
    
    return create_agent(
        model=sub_llm,
        tools=tools,
        system_prompt=system_prompt,
        state_schema=None,
        context_schema=None,
        middleware=[],
        checkpointer=None,
    )


def _get_task_system_prompt(has_image: bool, enable_tools: bool) -> str:
    """Generate system prompt for sub-agent based on capabilities."""
    base = (
        "You are a focused data processing assistant. "
        "Process the provided data according to the user's instructions. "
        "Be concise and structured in your output."
    )
    
    if has_image:
        base += " You have vision capabilities and can analyze images."
    
    if enable_tools:
        base += " You have access to file and directory tools to gather additional context if needed."
    
    return base

