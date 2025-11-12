"""Image operations for analyzing images with multi-modal models.

This module replaces image_ops.py with LangChain-compatible tools.

Phase 2 Status: Basic implementation.
Phase 3: Will integrate with multimodal LLM routing in middleware.
"""
import base64
from pathlib import Path
from urllib.parse import urlparse
import requests
from langchain_core.tools import tool


@tool
def load_image(file_path: str) -> str:
    """Load an image file for analysis with vision capabilities.

    Supports both local file paths and remote URLs (http/https).
    Supported formats: JPEG, PNG, GIF, WebP.

    Note: In Phase 3, this will trigger automatic switching to multimodal LLM.

    Args:
        file_path: Path to the image file (local path or URL)

    Returns:
        Confirmation message with image details
    """
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }

    try:
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
                if extension not in mime_types:
                    return f"Error: Unsupported image type: {extension}"
                mime_type = mime_types[extension]

            size_kb = len(image_data) / 1024

            # Note: In Phase 3, we'll return the base64 data and trigger multimodal
            # For now, just confirm the image was loaded
            return f"✓ Image loaded from URL: {file_path}\n" \
                   f"Type: {mime_type}\n" \
                   f"Size: {size_kb:.1f} KB\n" \
                   f"\n(Note: Multimodal analysis will be enabled in Phase 3)"

        else:
            # Handle local file
            path = Path(file_path)

            if not path.exists():
                return f"Error: Image file not found: {file_path}"

            extension = path.suffix.lower()
            if extension not in mime_types:
                return f"Error: Unsupported image type: {extension}. Supported: {', '.join(mime_types.keys())}"

            # Read image
            with open(file_path, 'rb') as f:
                image_data = f.read()

            size_kb = len(image_data) / 1024
            mime_type = mime_types[extension]
            abs_path = str(path.absolute())

            return f"✓ Image loaded: {abs_path}\n" \
                   f"Type: {mime_type}\n" \
                   f"Size: {size_kb:.1f} KB\n" \
                   f"\n(Note: Multimodal analysis will be enabled in Phase 3)"

    except requests.RequestException as e:
        return f"Error fetching remote image: {str(e)}"
    except Exception as e:
        return f"Error loading image: {str(e)}"


# Export tools as a list for easy import
IMAGE_TOOLS = [
    load_image
]
