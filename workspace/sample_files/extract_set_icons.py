import csv
import re
import os

# Read the input CSV file
input_file = 'japanese_pokemon_cards.csv'
output_file = 'output/set_icons.csv'

# Initialize list to store set code and image data
set_data = []

# Read the input CSV file
with open(input_file, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    headers = next(reader)  # Skip header row
    
    for row in reader:
        if len(row) < 8:  # Skip malformed rows
            continue
        
        set_no = row[0].strip()
        symbol_img = row[1].strip() if len(row) > 1 else ''
        logo_img = row[2].strip() if len(row) > 2 else ''
        
        # Extract image filenames from the markdown image syntax
        # Pattern: ![](./expansions_files/filename.png)
        image_pattern = r'!\[.*?\]\((./expansions_files/[^)]+\.png)\)'
        
        # Extract images from Symbol column
        symbol_images = re.findall(image_pattern, symbol_img)
        
        # Extract images from Logo column
        logo_images = re.findall(image_pattern, logo_img)
        
        # Combine all images for this set
        all_images = symbol_images + logo_images
        
        # If no images found, skip this row (unless it's a special case like Base Set)
        if not all_images and set_no != '1' and row[4] != 'Base Set':
            continue
        
        # Process each image for this set
        for img_path in all_images:
            # Extract just the filename from the path
            img_filename = os.path.basename(img_path)
            
            # Add to our data
            set_data.append({
                'Set No.': set_no,
                'Image File': img_filename,
                'Image Path': img_path
            })
        
        # Handle cases where there's no image in Symbol or Logo but we know the set
        if not all_images and set_no != '1' and row[4] == 'Base Set':
            # For Base Set, we know there should be an image
            # We'll try to find the appropriate image based on set name
            if row[5] == 'Base Set':
                # Look for Base Set image
                base_set_img = 'SetSymbolExpansion_Pack_20th_Anniversary.png'  # Most likely candidate
                set_data.append({
                    'Set No.': set_no,
                    'Image File': base_set_img,
                    'Image Path': f'./expansions_files/{base_set_img}'
                })

# Write to output CSV file
with open(output_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    
    # Write header
    writer.writerow(['Set No.', 'Image File', 'Image Path'])
    
    # Write data
    for item in set_data:
        writer.writerow([item['Set No.'], item['Image File'], item['Image Path']])

print(f"Successfully extracted {len(set_data)} set images to {output_file}")
