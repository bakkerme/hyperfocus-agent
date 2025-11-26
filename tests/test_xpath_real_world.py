#!/usr/bin/env python3
"""Test with a more realistic HTML structure similar to a blog or documentation site"""

from src.hyperfocus_agent.utils.html_utils import get_markdown_outline_from_html
from lxml import html as lhtml, etree

def test_xpath_real_world():
    # Realistic blog/documentation HTML
    html_sample = """
    <!DOCTYPE html>
    <html>
    <body>
        <article class="post">
            <header>
                <h1 id="main-title">Understanding Web Scraping</h1>
            </header>
            <section id="intro">
                <h2>Introduction</h2>
                <p>Web scraping is the process of extracting data from websites.</p>
            </section>
            <section id="basics">
                <h2>The Basics</h2>
                <h3>What You Need</h3>
                <ul><li>Python</li><li>Beautiful Soup</li></ul>
                <h3>Getting Started</h3>
                <p>First, install the required packages...</p>
                <h4>Installation Steps</h4>
                <p>Run pip install...</p>
            </section>
            <section id="advanced">
                <h2>Advanced Techniques</h2>
                <h3>XPath Selectors</h3>
                <p>XPath is powerful...</p>
                <h3>CSS Selectors</h3>
                <p>CSS selectors are simpler...</p>
            </section>
        </article>
    </body>
    </html>
    """

    outline = get_markdown_outline_from_html(html_sample)
    assert "Understanding Web Scraping" in outline
    assert "The Basics" in outline

    # Demonstrate using the XPath to extract content
    tree = lhtml.fromstring(html_sample)

    # Use one of the generated XPaths (simulated)
    xpath_basics = "//section[@id='basics']/h2"  # This will work

    elements = tree.xpath(xpath_basics)
    assert len(elements) > 0
    assert elements[0].text == "The Basics"
    
    # Get all content under this heading
    section = tree.xpath("//section[@id='basics']")[0]
    all_headings = section.xpath(".//h2 | .//h3 | .//h4")
    heading_texts = [h.text for h in all_headings]
    
    assert "The Basics" in heading_texts
    assert "What You Need" in heading_texts
    assert "Getting Started" in heading_texts
    assert "Installation Steps" in heading_texts
