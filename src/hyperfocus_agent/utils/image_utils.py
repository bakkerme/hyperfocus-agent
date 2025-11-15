"""Image loading utilities for handling local and remote images.

This module provides shared image loading functionality used by both
image_tools and task_tools for consistent image handling.
"""
import base64
import mimetypes
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlparse

import requests


class ImageData(TypedDict):
    """Structured image data after loading."""
    base64_data: str
    mime_type: str
    size_kb: float
    display_path: str


def load_image_as_base64(file_path: str, timeout: int = 30) -> ImageData:
    """Load an image from local file or URL and return base64-encoded data.
    
    Supports both local file paths and remote URLs (http/https).
    Automatically detects MIME type from file extension or HTTP headers.
    
    Args:
        file_path: Path to the image file (local path or URL)
        timeout: Timeout in seconds for remote requests (default: 30)
        
    Returns:
        Dictionary containing:
        - base64_data: Base64-encoded image data
        - mime_type: MIME type (e.g., 'image/jpeg')
        - size_kb: Size in kilobytes
        - display_path: Human-readable path for logging
        
    Raises:
        FileNotFoundError: If local file doesn't exist
        ValueError: If unsupported image format
        requests.RequestException: If remote fetch fails
        
    Examples:
        # Load local image
        data = load_image_as_base64('/path/to/image.jpg')
        
        # Load remote image
        data = load_image_as_base64('https://example.com/photo.png')
        
        # Use the data
        print(f"Loaded {data['mime_type']}, {data['size_kb']:.1f} KB")
        img_tag = f"data:{data['mime_type']};base64,{data['base64_data']}"
    """
    # Supported MIME types by extension
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
    }
    
    # Check if URL or local file
    parsed = urlparse(file_path)
    is_remote = parsed.scheme in ('http', 'https')
    
    if is_remote:
        # Handle remote URL
        response = requests.get(file_path, timeout=timeout)
        response.raise_for_status()
        image_data = response.content
        
        # Determine MIME type from Content-Type header or extension
        content_type = response.headers.get('content-type', '').lower()
        if 'image/' in content_type:
            mime_type = content_type.split(';')[0].strip()
        else:
            # Fall back to extension-based detection
            extension = Path(parsed.path).suffix.lower()
            if extension not in mime_types:
                raise ValueError(
                    f"Unsupported image type: {extension}. "
                    f"Supported: {', '.join(mime_types.keys())}"
                )
            mime_type = mime_types[extension]
        
        display_path = file_path
        
    else:
        # Handle local file
        path = Path(file_path).expanduser().resolve()
        
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {file_path}")
        
        if not path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")
        
        # Determine MIME type from extension
        extension = path.suffix.lower()
        
        # Try mimetypes library first, fall back to our map
        mime_type, _ = mimetypes.guess_type(str(path))
        if not mime_type or not mime_type.startswith("image/"):
            if extension not in mime_types:
                raise ValueError(
                    f"Unsupported image type: {extension}. "
                    f"Supported: {', '.join(mime_types.keys())}"
                )
            mime_type = mime_types[extension]
        
        # Read image data
        with open(path, 'rb') as f:
            image_data = f.read()
        
        display_path = str(path)
    
    # Encode to base64
    base64_encoded = base64.b64encode(image_data).decode('utf-8')
    size_kb = len(image_data) / 1024
    
    return {
        'base64_data': base64_encoded,
        'mime_type': mime_type,
        'size_kb': size_kb,
        'display_path': display_path,
    }
