#!/usr/bin/env python3
"""Test various grouping scenarios"""

from src.hyperfocus_agent.langchain_tools.web_tools import create_dom_skeleton

scenarios = [
    ("Identical children (should show [N type])", """
        <ul>
            <li><a>Link 1</a></li>
            <li><a>Link 2</a></li>
            <li><a>Link 3</a></li>
            <li><a>Link 4</a></li>
        </ul>
    """),

    ("Mixed children (should NOT show inline structure)", """
        <ul>
            <li><a>Link</a></li>
            <li><span>Text</span></li>
            <li><a>Link</a></li>
            <li><a>Link</a></li>
        </ul>
    """),

    ("Empty children (should NOT show inline structure)", """
        <ul>
            <li></li>
            <li></li>
            <li></li>
        </ul>
    """),

    ("Heading preservation (headings should not be grouped)", """
        <div>
            <p>Para 1</p>
            <p>Para 2</p>
            <h2>Important heading</h2>
            <p>Para 3</p>
            <p>Para 4</p>
            <p>Para 5</p>
        </div>
    """),
]

for title, html in scenarios:
    print(f"\n{'='*70}")
    print(f"{title}")
    print('='*70)
    _, skeleton = create_dom_skeleton(html, compact_threshold=3)
    print(skeleton)
