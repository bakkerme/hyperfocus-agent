"""Image operations for analyzing images with multi-modal models."""
import base64
import os
from pathlib import Path
from urllib.parse import urlparse
import requests
from .types import ChatCompletionToolParam


def load_image(file_path: str) -> dict:
    """
    Load an image file and return it in a format ready for multi-modal LLM processing.

    This function reads an image file from a local path or remote URL, encodes it as base64,
    and returns metadata that will trigger the system to switch to a multi-modal model for
    the next LLM call.

    Args:
        file_path: Path to the image file (local path or URL)

    Returns:
        A dictionary containing:
        - base64_data: The base64-encoded image data
        - mime_type: The MIME type of the image
        - file_path: The original file path or URL
        - use_multimodal: Flag to trigger multi-modal model switching

    Raises:
        FileNotFoundError: If the local image file doesn't exist
        ValueError: If the file is not a supported image type
        requests.RequestException: If remote image cannot be fetched
    """
    # Check if the path is a URL
    parsed = urlparse(file_path)
    is_remote = parsed.scheme in ('http', 'https')
    
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    
    if is_remote:
        # Handle remote URL
        response = requests.get(file_path, timeout=30)
        response.raise_for_status()
        image_data = response.content
        
        # Determine MIME type from Content-Type header or URL extension
        content_type = response.headers.get('content-type', '').lower()
        if 'image/' in content_type:
            mime_type = content_type.split(';')[0].strip()
        else:
            # Fall back to extension-based detection
            extension = Path(parsed.path).suffix.lower()
            if extension not in mime_types:
                raise ValueError(f"Unsupported image type: {extension}. Supported types: {', '.join(mime_types.keys())}")
            mime_type = mime_types[extension]
        
        base64_data = base64.b64encode(image_data).decode('utf-8')
        return {
            'base64_data': base64_data,
            'mime_type': mime_type,
            'file_path': file_path,
            'use_multimodal': True,
            'message': f"Image loaded from {file_path}"
        }
    else:
        # Handle local file
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {file_path}")

        # Determine MIME type from extension
        extension = path.suffix.lower()
        if extension not in mime_types:
            raise ValueError(f"Unsupported image type: {extension}. Supported types: {', '.join(mime_types.keys())}")

        # Read and encode the image
        with open(file_path, 'rb') as image_file:
            image_data = image_file.read()
            base64_data = base64.b64encode(image_data).decode('utf-8')

        return {
            'base64_data': base64_data,
            'mime_type': mime_types[extension],
            'file_path': str(path.absolute()),
            'use_multimodal': True,
            'message': f"Image loaded from {path.absolute()}"
        }


IMAGE_TOOLS: list[ChatCompletionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "load_image",
            "description": "Load an image file to analyze with vision capabilities. Supports both local file paths and remote URLs (http/https). This will switch to a multi-modal model for the next response. Supported formats: JPEG, PNG, GIF, WebP.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the image file (local path or URL starting with http:// or https://)"
                    }
                },
                "required": ["file_path"]
            }
        }
    }
]
