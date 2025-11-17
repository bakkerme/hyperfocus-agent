#!/usr/bin/env python3
"""Test with a more realistic HTML structure similar to a blog or documentation site"""

from src.hyperfocus_agent.utils.html_utils import get_markdown_outline_from_html
from lxml import html as lhtml, etree

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

print("=== Real-World Example: Blog Post Outline ===\n")
outline = get_markdown_outline_from_html(html_sample)
print(outline)
print("\n" + "="*60)

# Demonstrate using the XPath to extract content
print("\n=== Demonstrating XPath Usage ===\n")
tree = lhtml.fromstring(html_sample)

# Use one of the generated XPaths
xpath = "//h2[@id='second']"  # This won't exist
xpath_basics = "//section[@id='basics']/h2"  # This will work

print(f"Extracting with XPath: {xpath_basics}")
elements = tree.xpath(xpath_basics)
if elements:
    print(f"Found: {elements[0].text}")
    # Get all content under this heading
    section = tree.xpath("//section[@id='basics']")[0]
    all_headings = section.xpath(".//h2 | .//h3 | .//h4")
    print(f"All headings in this section: {[h.text for h in all_headings]}")

print("\n" + "="*60)
print("\nBenefits of XPath-Enhanced Outline:")
print("1. ✓ Semantic structure (markdown headings)")
print("2. ✓ Exact HTML location (XPath)")
print("3. ✓ Can extract content around headings")
print("4. ✓ Can build selectors for nested elements")
print("5. ✓ Works with both ID-based and position-based selection")
