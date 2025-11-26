#!/usr/bin/env python3
"""Test script to demonstrate the XPath-enhanced markdown outline"""

from src.hyperfocus_agent.utils.html_utils import get_markdown_outline_from_html

def test_xpath_outline():
    # Sample HTML with various heading structures
    html_sample = """
    <!DOCTYPE html>
    <html>
    <head><title>Test Page</title></head>
    <body>
        <div id="header">
            <h1>Main Title</h1>
        </div>
        <div class="content">
            <h2>First Section</h2>
            <p>Some content here</p>
            <div class="subsection">
                <h3>Subsection A</h3>
                <p>More content</p>
                <h3>Subsection B</h3>
                <p>Even more content</p>
            </div>
            <h2 id="second">Second Section</h2>
            <div>
                <h3>Another Subsection</h3>
                <h4>Deep Heading</h4>
            </div>
        </div>
        <footer>
            <h2>Footer Section</h2>
        </footer>
    </body>
    </html>
    """

    outline = get_markdown_outline_from_html(html_sample)
    
    # Assertions
    assert "Main Title" in outline
    assert "First Section" in outline
    assert "Subsection A" in outline
    assert "xpath:" in outline or "XPath:" in outline or "//" in outline, "Should contain XPath info"
