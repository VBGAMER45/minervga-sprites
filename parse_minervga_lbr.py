#!/usr/bin/env python3
"""
MINERVGA.LBR Sprite Library Parser

This script parses the custom sprite library format used by MinerVGA (1989).
The format stores 16x24 pixel sprites using VGA planar format (4 bit planes).

Format:
- Header: "LibraryName",sprite_count
- Sprites: index,"name",width,height,plane_data...,terminator

The pixel data is stored as signed 16-bit integers, with 4 values per row
(one per VGA color plane). Each integer represents 16 horizontal pixels
as a bitmask.
"""

import os
import csv
from PIL import Image
import struct

# VGA Mode 12 default 16-color palette (approximate RGB values)
VGA_PALETTE = [
    (0, 0, 0),        # 0: Black
    (0, 0, 170),      # 1: Blue
    (0, 170, 0),      # 2: Green
    (0, 170, 170),    # 3: Cyan
    (170, 0, 0),      # 4: Red
    (170, 0, 170),    # 5: Magenta
    (170, 85, 0),     # 6: Brown
    (170, 170, 170),  # 7: Light Gray
    (85, 85, 85),     # 8: Dark Gray
    (85, 85, 255),    # 9: Light Blue
    (85, 255, 85),    # 10: Light Green
    (85, 255, 255),   # 11: Light Cyan
    (255, 85, 85),    # 12: Light Red
    (255, 85, 255),   # 13: Light Magenta
    (255, 255, 85),   # 14: Yellow
    (255, 255, 255),  # 15: White
]

def signed_to_unsigned_16(val):
    """Convert signed 16-bit int to unsigned"""
    if val < 0:
        return val + 65536
    return val

def extract_bits(value, num_bits=16):
    """Extract individual bits from a 16-bit value, MSB first, then swap halves"""
    bits = []
    for i in range(num_bits - 1, -1, -1):
        bits.append((value >> i) & 1)
    # Swap left and right halves (bits 0-7 and 8-15)
    return bits[8:16] + bits[0:8]

def parse_sprite_data(data_values, width, height):
    """
    Parse planar VGA sprite data into a 2D pixel array.
    
    VGA Mode 12 uses 4 bit planes. Each row of 16 pixels is stored as
    4 consecutive 16-bit integers (one per plane).
    """
    pixels = []
    
    # Calculate values per row (width / 16 bits * 4 planes)
    words_per_row = (width // 16) * 4
    if width % 16 != 0:
        words_per_row = 4  # For 16-pixel wide sprites
    
    data_idx = 0
    
    for row in range(height):
        row_pixels = []
        
        # Get the 4 plane values for this row
        if data_idx + 4 > len(data_values):
            print(f"Warning: Not enough data at row {row}, padding with zeros")
            plane_values = [0, 0, 0, 0]
        else:
            plane_values = []
            for p in range(4):
                val = int(data_values[data_idx + p])
                plane_values.append(signed_to_unsigned_16(val))
        
        data_idx += 4
        
        # Extract bits from each plane
        plane_bits = [extract_bits(pv) for pv in plane_values]
        
        # Combine planes to get pixel colors
        for x in range(width):
            if x < 16:
                color = (
                    (plane_bits[0][x] << 0) |
                    (plane_bits[1][x] << 1) |
                    (plane_bits[2][x] << 2) |
                    (plane_bits[3][x] << 3)
                )
            else:
                color = 0
            row_pixels.append(color)
        
        pixels.append(row_pixels)
    
    return pixels

def create_sprite_image(pixels, scale=4):
    """Create a PIL Image from pixel data with optional scaling"""
    height = len(pixels)
    width = len(pixels[0]) if pixels else 0
    
    img = Image.new('RGB', (width * scale, height * scale))
    
    for y, row in enumerate(pixels):
        for x, color_idx in enumerate(row):
            rgb = VGA_PALETTE[color_idx % 16]
            # Draw scaled pixel
            for sy in range(scale):
                for sx in range(scale):
                    img.putpixel((x * scale + sx, y * scale + sy), rgb)
    
    return img

def parse_lbr_file(filepath):
    """Parse the MINERVGA.LBR file and return sprite data"""
    sprites = []
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Parse as CSV-like format
    lines = content.strip().split('\n')
    
    # Parse header
    header_parts = lines[0].split(',')
    library_name = header_parts[0].strip('"')
    sprite_count = int(header_parts[1])
    
    print(f"Library: {library_name}")
    print(f"Sprite count: {sprite_count}")
    print()
    
    # Parse each sprite
    for line_num, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
            
        # Parse the CSV-like line
        # Format: index,"name",width,height,data...
        parts = []
        in_quotes = False
        current = ""
        
        for char in line:
            if char == '"':
                in_quotes = not in_quotes
                current += char
            elif char == ',' and not in_quotes:
                parts.append(current.strip())
                current = ""
            else:
                current += char
        if current:
            parts.append(current.strip())
        
        if len(parts) < 5:
            print(f"Skipping invalid line {line_num}: too few parts")
            continue
        
        try:
            sprite_idx = int(parts[0])
            sprite_name = parts[1].strip('"')
            width = int(parts[2])
            height = int(parts[3])
            data_values = parts[4:]
            
            # Remove trailing terminator values (usually last 2 values)
            # Based on analysis, sprites have ~96 data values for 16x24
            expected_data = (width // 16) * 4 * height
            if expected_data == 0:
                expected_data = 4 * height  # minimum 4 per row
            
            # Trim to expected data length
            if len(data_values) > expected_data:
                data_values = data_values[:expected_data]
            
            sprites.append({
                'index': sprite_idx,
                'name': sprite_name,
                'width': width,
                'height': height,
                'data': data_values
            })
            
        except (ValueError, IndexError) as e:
            print(f"Error parsing line {line_num}: {e}")
            continue
    
    return library_name, sprites

def main():
    input_file = '/mnt/user-data/uploads/MINERVGA.LBR'
    output_dir = '/home/claude/minervga_sprites'
    output_dir_1x = '/home/claude/minervga_sprites_1x'
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(output_dir_1x, exist_ok=True)
    
    library_name, sprites = parse_lbr_file(input_file)
    
    print(f"Parsed {len(sprites)} sprites")
    print()
    
    # Process each sprite
    for sprite in sprites:
        print(f"Processing sprite {sprite['index']:2d}: {sprite['name']}")
        
        # Parse pixel data
        pixels = parse_sprite_data(
            sprite['data'], 
            sprite['width'], 
            sprite['height']
        )
        
        # Clean filename
        safe_name = sprite['name'].replace('/', '_').replace('\\', '_')
        filename = f"{sprite['index']:02d}_{safe_name}.png"
        
        # Create and save image (scaled 4x for visibility)
        img_4x = create_sprite_image(pixels, scale=4)
        filepath_4x = os.path.join(output_dir, filename)
        img_4x.save(filepath_4x)
        
        # Create and save original 1x size
        img_1x = create_sprite_image(pixels, scale=1)
        filepath_1x = os.path.join(output_dir_1x, filename)
        img_1x.save(filepath_1x)
    
    print()
    print(f"Sprites (4x) saved to: {output_dir}")
    print(f"Sprites (1x) saved to: {output_dir_1x}")
    
    # Also create sprite sheets with all sprites
    print("Creating sprite sheets...")
    
    sprites_per_row = 10
    
    # 4x scaled spritesheet
    sprite_width_4x = 16 * 4
    sprite_height_4x = 24 * 4
    padding_4x = 4
    
    num_rows = (len(sprites) + sprites_per_row - 1) // sprites_per_row
    
    sheet_width_4x = sprites_per_row * (sprite_width_4x + padding_4x) + padding_4x
    sheet_height_4x = num_rows * (sprite_height_4x + padding_4x) + padding_4x
    
    sheet_4x = Image.new('RGB', (sheet_width_4x, sheet_height_4x), (32, 32, 32))
    
    for i, sprite in enumerate(sprites):
        row = i // sprites_per_row
        col = i % sprites_per_row
        
        x = col * (sprite_width_4x + padding_4x) + padding_4x
        y = row * (sprite_height_4x + padding_4x) + padding_4x
        
        pixels = parse_sprite_data(sprite['data'], sprite['width'], sprite['height'])
        img = create_sprite_image(pixels, scale=4)
        
        sheet_4x.paste(img, (x, y))
    
    sheet_path_4x = os.path.join(output_dir, 'spritesheet.png')
    sheet_4x.save(sheet_path_4x)
    print(f"Sprite sheet (4x) saved to: {sheet_path_4x}")
    
    # 1x original size spritesheet
    sprite_width_1x = 16
    sprite_height_1x = 24
    padding_1x = 1
    
    sheet_width_1x = sprites_per_row * (sprite_width_1x + padding_1x) + padding_1x
    sheet_height_1x = num_rows * (sprite_height_1x + padding_1x) + padding_1x
    
    sheet_1x = Image.new('RGB', (sheet_width_1x, sheet_height_1x), (32, 32, 32))
    
    for i, sprite in enumerate(sprites):
        row = i // sprites_per_row
        col = i % sprites_per_row
        
        x = col * (sprite_width_1x + padding_1x) + padding_1x
        y = row * (sprite_height_1x + padding_1x) + padding_1x
        
        pixels = parse_sprite_data(sprite['data'], sprite['width'], sprite['height'])
        img = create_sprite_image(pixels, scale=1)
        
        sheet_1x.paste(img, (x, y))
    
    sheet_path_1x = os.path.join(output_dir_1x, 'spritesheet.png')
    sheet_1x.save(sheet_path_1x)
    print(f"Sprite sheet (1x) saved to: {sheet_path_1x}")
    
    # Save sprite index/documentation
    doc_path = os.path.join(output_dir, 'sprite_index.txt')
    with open(doc_path, 'w') as f:
        f.write(f"MINERVGA Sprite Library\n")
        f.write(f"=======================\n\n")
        f.write(f"Library Name: {library_name}\n")
        f.write(f"Total Sprites: {len(sprites)}\n")
        f.write(f"Sprite Size: 16x24 pixels\n")
        f.write(f"Format: VGA Mode 12 (4-plane, 16 colors)\n\n")
        f.write(f"Sprite Index:\n")
        f.write(f"-------------\n")
        for sprite in sprites:
            f.write(f"{sprite['index']:2d}: {sprite['name']}\n")
    
    print(f"Documentation saved to: {doc_path}")

if __name__ == '__main__':
    main()
