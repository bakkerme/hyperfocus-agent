#!/usr/bin/env python3
"""Test the DOM skeleton with the actual pokemon.html file"""

from src.hyperfocus_agent.langchain_tools.web_tools import create_dom_skeleton

# Read the pokemon.html file
with open('workspace/sample_files/pokemon.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

print("=" * 80)
print("POKEMON.HTML - COMPACT DOM SKELETON (compact_threshold=3)")
print("=" * 80)
_, skeleton_compact = create_dom_skeleton(html_content, compact_threshold=3)
print(skeleton_compact)

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"HTML file size: {len(html_content):,} characters")
print(f"Skeleton size: {len(skeleton_compact):,} characters")
print(f"Skeleton lines: {skeleton_compact.count(chr(10))+1}")
