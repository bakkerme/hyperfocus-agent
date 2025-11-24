"""Standalone OCR utility for extracting text from images.

This module provides both a CLI command and reusable function for performing
OCR on images using multimodal LLMs.

Usage as CLI:
    ocr /path/to/image.jpg
    ocr https://example.com/screenshot.png
    ocr /path/to/image.jpg --prompt "Focus on handwritten totals"

Usage as Python function:
    from hyperfocus_agent.ocr import ocr_image

    text = ocr_image('/path/to/image.jpg')
    print(text)

    text = ocr_image('/path/to/image.jpg', prompt_instructions="Only capture the receipt total")
    print(text)
"""
import argparse
import sys
from typing import Optional

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from .model_config import ModelConfig
from .utils.image_utils import load_image_as_base64


def ocr_image(
    file_path: str,
    timeout: int = 30,
    prompt_instructions: Optional[str] = None,
) -> str:
    """Perform OCR on an image file and extract text content.

    Supports both local file paths and remote URLs (http/https).
    Supported formats: JPEG, PNG, GIF, WebP, BMP.

    Args:
        file_path: Path to the image file (local path or URL)
        timeout: Timeout in seconds for remote image fetches (default: 30)
        prompt_instructions: Optional extra instructions appended to the OCR prompt

    Returns:
        Extracted text content from the image

    Raises:
        FileNotFoundError: If local file doesn't exist
        ValueError: If unsupported image format or no multimodal model configured
        Exception: If OCR extraction fails

    Examples:
        # Extract text from local image
        text = ocr_image('/path/to/receipt.jpg')

        # Extract text from remote image
        text = ocr_image('https://example.com/document.png')

        # Use in a script
        import sys
        from hyperfocus_agent.ocr import ocr_image

        for image_path in sys.argv[1:]:
            print(f"Processing {image_path}...")
            text = ocr_image(image_path)
            print(text)
            print("---")
    """
    # Load model configuration (silent mode)
    config = ModelConfig.from_environment(verbose=False)

    if not config.multimodal:
        raise ValueError(
            "No multimodal model configured. Please set MULTIMODAL_OPENAI_BASE_URL, "
            "MULTIMODAL_OPENAI_API_KEY, and MULTIMODAL_OPENAI_MODEL environment variables."
        )

    # Load image as base64
    image_data = load_image_as_base64(file_path, timeout=timeout)

    # Create non-streaming multimodal model for OCR
    ocr_llm = ChatOpenAI(
        model=config.multimodal.model_name,  # type: ignore
        api_key=config.multimodal.openai_api_key,  # type: ignore
        base_url=config.multimodal.openai_api_base,  # type: ignore
        temperature=0,
        streaming=False,
    )

    # Create simple agent without tools
    agent = create_agent(
        model=ocr_llm,
        tools=[],
        system_prompt=(
            "You are an OCR assistant. Extract all text from the provided image. "
            "Return the extracted text with an overview of the structure of the text, including the position of elements."
            "Don't say 'of course' or other filler, just provide the requested information."
        ),
        state_schema=None,
        context_schema=None,
        middleware=[],
        checkpointer=None,
    )

    message = HumanMessage(
        content=[
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{image_data['mime_type']};base64,{image_data['base64_data']}"
                }
            },
        ]
    )

    # Execute OCR
    result = agent.invoke(
        {"messages": [message]},  # type: ignore
        config={"recursion_limit": 5}
    )

    # Extract response
    output_messages = result.get("messages", [])
    if not output_messages:
        raise Exception("No response from OCR model")

    return output_messages[-1].content


def main() -> None:
    """CLI entry point for OCR command.

    Usage:
        ocr /path/to/image.jpg
        ocr https://example.com/screenshot.png
    """
    parser = argparse.ArgumentParser(
        prog="ocr",
        description="Perform OCR on an image file or URL and extract text content.",
    )
    parser.add_argument(
        "image_path",
        help="Path or URL of the image to process",
    )
    parser.add_argument(
        "--prompt",
        dest="prompt_instructions",
        help="Optional extra instructions appended to the OCR prompt.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout in seconds for remote image fetches (default: 30).",
    )

    args = parser.parse_args()

    try:
        print(f"→ Processing: {args.image_path}", file=sys.stderr)
        text = ocr_image(
            args.image_path,
            timeout=args.timeout,
            prompt_instructions=args.prompt_instructions,
        )
        print(text)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: OCR failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
