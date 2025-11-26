#!/usr/bin/env python3
"""
Demonstrate how the unified markdown outline bridges semantic structure with HTML extraction.

This shows the power of having both:
1. Human-readable markdown outline (semantic)
2. Machine-executable selectors (technical)
"""

from src.hyperfocus_agent.utils.html_utils import get_markdown_outline_from_html
from lxml import html as lhtml
from lxml.cssselect import CSSSelector

def test_unified_outline():
    # Complex news website structure
    html_sample = """
    <!DOCTYPE html>
    <html>
    <body>
        <nav id="main-nav">
            <h2>Navigation</h2>
        </nav>
        <main>
            <article class="featured-post">
                <h1 id="article-title">Breaking: AI Agents Now Write Their Own Documentation</h1>
                <section class="article-content">
                    <h2>Overview</h2>
                    <p>In a stunning development...</p>

                    <h2>Key Points</h2>
                    <div class="key-points">
                        <h3>Impact on Developers</h3>
                        <p>Developers are reporting...</p>
                        <h3>Industry Response</h3>
                        <p>Tech giants have responded...</p>
                    </div>

                    <h2>Technical Details</h2>
                    <div class="technical-section">
                        <h3>Architecture</h3>
                        <h4>Component Design</h4>
                        <p>The system uses...</p>
                        <h4>Data Flow</h4>
                        <p>Information flows through...</p>
                    </div>
                </section>
            </article>
            <aside class="related">
                <h2>Related Articles</h2>
                <article>
                    <h3>Previous Breakthroughs</h3>
                </article>
            </aside>
        </main>
    </body>
    </html>
    """

    outline = get_markdown_outline_from_html(html_sample)
    
    # Assertions
    assert "Breaking: AI Agents Now Write Their Own Documentation" in outline
    assert "Technical Details" in outline
    
    # Parse for extraction
    tree = lhtml.fromstring(html_sample)

    # Using the CSS selector from the outline (simulated check)
    css = "article.featured-post > section.article-content > h2:nth-of-type(3)"
    
    # Extract the heading
    heading = tree.cssselect(css)[0]
    assert heading.text == "Technical Details"

    # Now get all content under this heading
    xpath = "//h2[text()='Technical Details']/following-sibling::div[1]//h3 | //h2[text()='Technical Details']/following-sibling::div[1]//h4"
    subheadings = tree.xpath(xpath)
    
    subheading_texts = [sh.text for sh in subheadings]
    assert "Architecture" in subheading_texts
    assert "Component Design" in subheading_texts
    assert "Data Flow" in subheading_texts
