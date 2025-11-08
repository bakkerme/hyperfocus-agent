import requests

from .types import ChatCompletionToolParam

def readable_web_get(url: str) -> str:
    """Fetch and return the content of a web page in an LLM-readable format, via jina.ai reader."""
    response = requests.get(f"https://r.jina.ai/{url}")
    response.raise_for_status()
    return response.text

def raw_web_get(url: str) -> str:
    """Fetch and return the raw content of a web page."""
    response = requests.get(url)
    response.raise_for_status()
    return response.text

WEB_TOOLS: list[ChatCompletionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "readable_web_get",
            "description": "Fetches and returns the content of a web page in an LLM-readable format. This is useful for regular web content consumption.",
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
    {
        "type": "function",
        "function": {
            "name": "raw_web_get",
            "description": "Fetches and returns the raw content of a web page. This should only be used if the user specifically requests raw HTML content, or wants to act upon the HTML structure of a page.",
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
    }
]