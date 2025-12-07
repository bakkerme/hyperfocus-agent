#!/usr/bin/env python3
"""Convert markdown tables from jp_cards.md to CSV format."""

import re
import csv

def parse_md_table(lines):
    """Parse a markdown table from a list of lines."""
    if not lines:
        return None

    # Remove separator line (the one with dashes)
    table_lines = [line for line in lines if not re.match(r'^\|[-:\s|]+\|$', line)]

    if not table_lines:
        return None

    rows = []
    for line in table_lines:
        # Split by pipe and clean up
        cells = [cell.strip() for cell in line.split('|')]
        # Remove empty first and last elements (from leading/trailing pipes)
        if cells and cells[0] == '':
            cells = cells[1:]
        if cells and cells[-1] == '':
            cells = cells[:-1]
        rows.append(cells)

    return rows

def extract_tables_from_md(filename):
    """Extract all tables from a markdown file."""
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    tables = []
    current_section = None
    current_table = []
    in_table = False

    for i, line in enumerate(lines):
        # Check for section header
        if line.startswith('## '):
            current_section = line[3:].strip()

        # Check if line is part of a table
        if line.strip().startswith('|'):
            in_table = True
            current_table.append(line)
        else:
            # If we were in a table and now we're not, save it
            if in_table and current_table:
                parsed_table = parse_md_table(current_table)
                if parsed_table and len(parsed_table) > 1:  # Must have header + at least one row
                    tables.append({
                        'section': current_section,
                        'rows': parsed_table
                    })
                current_table = []
                in_table = False

    # Don't forget the last table if file ends with it
    if current_table:
        parsed_table = parse_md_table(current_table)
        if parsed_table and len(parsed_table) > 1:
            tables.append({
                'section': current_section,
                'rows': parsed_table
            })

    return tables

def sanitize_filename(name):
    """Convert section name to valid filename."""
    # Remove special characters and replace spaces with underscores
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'[-\s]+', '_', name)
    return name.lower()

def main():
    input_file = 'jp_cards.md'
    tables = extract_tables_from_md(input_file)

    print(f"Found {len(tables)} tables")

    # Create a combined CSV with all tables
    all_rows = []
    for table in tables:
        section = table['section'] or 'Unknown'

        # Add section header row
        all_rows.append([f"=== {section} ==="])
        all_rows.append([])  # Empty row

        # Add table rows
        all_rows.extend(table['rows'])
        all_rows.append([])  # Empty row between tables

    # Write combined CSV
    output_file = 'jp_cards_all.csv'
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(all_rows)

    print(f"Created combined CSV: {output_file}")

    # Also create individual CSV files per section
    for table in tables:
        section = table['section'] or 'Unknown'
        filename = f"jp_cards_{sanitize_filename(section)}.csv"

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(table['rows'])

        print(f"Created {filename} with {len(table['rows'])-1} data rows")

if __name__ == '__main__':
    main()
