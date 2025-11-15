"""Image operations for analyzing images with multi-modal models.

This module replaces image_ops.py with LangChain-compatible tools.

Phase 3: Implements full multimodal support with automatic LLM routing.
"""
from langchain.tools import tool, ToolRuntime
from langchain_core.messages import ToolMessage, HumanMessage
from langgraph.types import Command

from hyperfocus_agent.langchain_tools.task_tools import run_task

from ..utils.image_utils import load_image_as_base64
from .task_tools import execute_task

@tool
def load_image(file_path: str, runtime: ToolRuntime) -> ToolMessage | Command:
    """Load an image file for analysis with vision capabilities. Can perform image analysis and OCR.

    Supports both local file paths and remote URLs (http/https).
    Supported formats: JPEG, PNG, GIF, WebP.

    Args:
        file_path: Path to the image file (local path or URL)

    Returns:
        Confirmation message that image was loaded successfully
    """
    try:
        result = load_image_as_base64(file_path)
        base64_data = result['base64_data']
        mime_type = result['mime_type']
        size_kb = result['size_kb']
        display_path = result['display_path']

        message = (
            f"✓ Image loaded successfully: {display_path}\n"
            f"  Type: {mime_type}\n"
            f"  Size: {size_kb:.1f} KB\n"
            f"\n"
            f"The image has been automatically injected into the conversation.\n"
            f"You can now analyze it with the multimodal vision model."
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(content=message, tool_call_id=runtime.tool_call_id),
                    HumanMessage(
                        content=[
                            {
                                "type": "image",
                                "source_type": "base64",
                                "data": base64_data,
                                "mime_type": mime_type
                            }
                        ]
                    )
                ],
            }
        )

    except FileNotFoundError as e:
        return ToolMessage(content=str(e), tool_call_id=runtime.tool_call_id)
    except ValueError as e:
        return ToolMessage(content=str(e), tool_call_id=runtime.tool_call_id)
    except Exception as e:
        return ToolMessage(content=f"Error loading image: {str(e)}", tool_call_id=runtime.tool_call_id)

@tool
def load_and_ocr_image(file_path: str, runtime: ToolRuntime) -> ToolMessage | Command:
    """Load an image file and perform OCR to extract text content.

    Supports both local file paths and remote URLs (http/https).
    Supported formats: JPEG, PNG, GIF, WebP.

    Args:
        file_path: Path to the image file (local path or URL)

    Returns:
        Extracted text content from the image
    """
    try:
        task_output = execute_task("Perform OCR on the provided image. Return only the extracted text without additional commentary.",
            image_path=file_path
        )

        return ToolMessage(content=task_output, tool_call_id=runtime.tool_call_id)
                
    except (FileNotFoundError, ValueError) as e:
        return ToolMessage(content=str(e), tool_call_id=runtime.tool_call_id)
    except Exception as e:
        return ToolMessage(content=f"Error loading image: {str(e)}", tool_call_id=runtime.tool_call_id)


# Export tools as a list for easy import
IMAGE_TOOLS = [
    load_image,
    load_and_ocr_image
]
