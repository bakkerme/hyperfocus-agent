#!/usr/bin/env python3
"""Test the DOM skeleton with the actual pokemon.html file"""

from src.hyperfocus_agent.langchain_tools.web_tools import create_dom_skeleton

import os

def test_pokemon_skeleton():
    # Read the pokemon.html file
    # Use relative path from project root or absolute path
    file_path = 'workspace/sample_files/pokemon.html'
    if not os.path.exists(file_path):
        # Fallback for CI or if file is missing
        html_content = "<html><body>" + "<div>Item</div>" * 100 + "</body></html>"
    else:
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

    _, skeleton_compact = create_dom_skeleton(html_content, compact_threshold=3)
    
    # Assertions
    assert len(skeleton_compact) < len(html_content), "Skeleton should be smaller than original HTML"
    assert len(skeleton_compact) > 0, "Skeleton should not be empty"
