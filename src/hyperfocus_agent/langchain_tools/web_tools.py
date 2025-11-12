"""Web scraping tools migrated to LangChain @tool decorator pattern.

This module replaces web_ops.py with LangChain-compatible tools.

Phase 2 Status: Basic implementation without full data store integration.
Phase 3: Will add full stateful web scraping with section extraction.
"""
import requests
import html2text
from langchain_core.tools import tool


@tool
def readable_web_get(url: str) -> str:
    """Fetch and return the content of a web page in LLM-readable markdown format.

    Converts HTML to clean markdown that's easy to read and process.

    Args:
        url: The URL to fetch

    Returns:
        The page content converted to markdown format
    """
    # Fetch the page
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # Fix encoding issues
        if (response.encoding and response.encoding.lower() in ('iso-8859-1', 'windows-1252')
            and response.apparent_encoding and 'utf' in response.apparent_encoding.lower()):
            response.encoding = 'utf-8'

        # Convert HTML to markdown
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.ignore_emphasis = False
        h.unicode_snob = True
        h.body_width = 0  # Don't wrap lines

        markdown_content = h.handle(response.text)

        # Note: In Phase 3, we'll add:
        # - Heading extraction
        # - Data store integration for section retrieval
        # - DOM skeleton generation
        # - CSS/XPath selectors

        return f"# Content from {url}\n\n{markdown_content}"

    except requests.RequestException as e:
        return f"Error fetching URL: {str(e)}"
    except Exception as e:
        return f"Error processing page: {str(e)}"


# Phase 2: Simplified tools list
# Phase 3 will add: get_readable_web_section, retrieve_stored_readable_web_section,
# load_page_for_navigation, get_dom_skeleton, extract_with_css, extract_with_xpath

WEB_TOOLS = [
    readable_web_get
]
