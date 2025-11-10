import requests
from readability import Document
import html2text

from .types import ChatCompletionToolParam


def readable_web_get(url: str) -> str:
    """
    Fetch and return the content of a web page in an LLM-readable format.

    Pipeline:
    1. Fetch raw HTML with requests
    2. Extract main content with readability-lxml
    3. Convert HTML to clean markdown with html2text

    Args:
        url: The URL to fetch

    Returns:
        Clean markdown text of the main content
    """
    # Step 1: Fetch raw HTML
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    # Step 2: Extract main content with readability
    doc = Document(response.text)
    clean_html = doc.summary()

    print(clean_html)

    # Get the title as well
    title = doc.title()

    # Step 3: Convert to markdown
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.ignore_emphasis = False
    h.body_width = 0  # Don't wrap lines

    markdown_content = h.handle(clean_html)

    # Combine title and content
    result = f"# {title}\n\n{markdown_content}"

    print(result)

    return result

# def raw_web_get(url: str) -> str:
#     """Fetch and return the raw content of a web page."""
#     response = requests.get(url)
#     response.raise_for_status()
#     return response.text

WEB_TOOLS: list[ChatCompletionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "readable_web_get",
            "description": "Fetches and returns the content of a web page in an LLM-readable format. If the user asks for specific information from a web page, use this function to retrieve and summarize the content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the web page to fetch"
                    }
                },
                "required": ["url"]
            }
        }
    },
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "raw_web_get",
    #         "description": "Fetches and returns the raw content of a web page. Do not use this function unless the user specifically requests raw HTML content, or wants to act upon the HTML structure of a page.",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "url": {
    #                     "type": "string",
    #                     "description": "The URL of the web page to fetch"
    #                 }
    #             },
    #             "required": ["url"]
    #         }
    #     }
    # }
]