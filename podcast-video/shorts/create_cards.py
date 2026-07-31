#!/usr/bin/env python3
"""
Card Generator - Create intro and outro cards for short-form videos
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import json
from pathlib import Path


# Chapter theme colors
THEMES = {
    "Intro": {"color": "#0080FF", "icon": "💡"},
    "How Distillation Works": {"color": "#8B5CF6", "icon": "⚙️"},
    "The Pricing War": {"color": "#EF4444", "icon": "📉"},
    "Micro-Distillation for Solopreneurs": {"color": "#10B981", "icon": "🧩"},
    "Non-Technical Operator Framework": {"color": "#F97316", "icon": "📊"},
    "Operational Portability Strategy": {"color": "#06B6D4", "icon": "🔄"},
    "Recap": {"color": "#FBBF24", "icon": "✓"}
}


def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def create_intro_card(chapter_number, chapter_title, total_chapters, output_path,
                      brand_name="Daily AI Pulse", theme_color=None):
    """
    Create intro card for a chapter

    Args:
        chapter_number: 1-7
        chapter_title: "How Distillation Works"
        total_chapters: 7
        output_path: Where to save the card
        brand_name: Podcast/brand name
        theme_color: Hex color (or auto-selected from theme)
    """
    # Canvas
    width, height = 1080, 1920
    img = Image.new('RGB', (width, height), color=(10, 10, 10))
    draw = ImageDraw.Draw(img)

    # Get theme
    theme = THEMES.get(chapter_title, {"color": "#FFFFFF", "icon": "•"})
    if theme_color:
        theme["color"] = theme_color

    accent_color = hex_to_rgb(theme["color"])

    # Fonts (fallback to system fonts)
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 96, index=1)  # Bold
        subtitle_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
        meta_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
    except:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        meta_font = ImageFont.load_default()

    # Top accent bar
    draw.rectangle([0, 0, width, 8], fill=accent_color)

    # Brand name (top)
    brand_y = 200
    draw.text((width // 2, brand_y), brand_name,
             fill=(150, 150, 150), font=meta_font, anchor="mm")

    # Chapter indicator
    indicator_y = 300
    indicator_text = f"Chapter {chapter_number} of {total_chapters}"
    draw.text((width // 2, indicator_y), indicator_text,
             fill=(110, 110, 110), font=meta_font, anchor="mm")

    # Icon/emoji (if supported)
    icon_y = 500
    icon_size = 200
    # Draw colored circle background
    circle_bbox = [
        width // 2 - icon_size // 2,
        icon_y - icon_size // 2,
        width // 2 + icon_size // 2,
        icon_y + icon_size // 2
    ]
    draw.ellipse(circle_bbox, fill=accent_color + (40,), outline=accent_color, width=4)

    # Title (wrapped if needed)
    title_y = 800
    title_words = chapter_title.split()

    # Simple word wrapping
    lines = []
    current_line = []
    for word in title_words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=title_font)
        if bbox[2] - bbox[0] > width - 100:  # 50px margin each side
            if current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                lines.append(word)
                current_line = []
        else:
            current_line.append(word)

    if current_line:
        lines.append(' '.join(current_line))

    # Draw wrapped title
    line_height = 110
    start_y = title_y - (len(lines) - 1) * line_height // 2

    for i, line in enumerate(lines):
        y = start_y + i * line_height
        draw.text((width // 2, y), line,
                 fill=(255, 255, 255), font=title_font, anchor="mm")

    # Accent line at bottom
    draw.rectangle([0, height - 8, width, height], fill=accent_color)

    # Save
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, quality=95)

    return output_path


def create_outro_card(output_path, brand_handle="@dailyaipulse",
                      cta_text="Full Episode Available", theme_color=None):
    """
    Create outro/CTA card

    Args:
        output_path: Where to save the card
        brand_handle: Social media handle
        cta_text: Call to action text
        theme_color: Hex color for accent
    """
    # Canvas
    width, height = 1080, 1920
    img = Image.new('RGB', (width, height), color=(10, 10, 10))
    draw = ImageDraw.Draw(img)

    # Theme color
    if theme_color:
        accent_color = hex_to_rgb(theme_color)
    else:
        accent_color = (255, 90, 0)  # Default orange

    # Fonts
    try:
        cta_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 72, index=1)
        handle_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 96, index=1)
        subtitle_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 42)
    except:
        cta_font = ImageFont.load_default()
        handle_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()

    # Accent bars (top and bottom)
    draw.rectangle([0, 0, width, 8], fill=accent_color)
    draw.rectangle([0, height - 8, width, height], fill=accent_color)

    # CTA text
    cta_y = 700
    draw.text((width // 2, cta_y), cta_text,
             fill=(200, 200, 200), font=cta_font, anchor="mm")

    # Brand handle (larger, prominent)
    handle_y = 960
    draw.text((width // 2, handle_y), brand_handle,
             fill=(255, 255, 255), font=handle_font, anchor="mm")

    # Subtitle
    subtitle_y = 1100
    draw.text((width // 2, subtitle_y), "YouTube • Spotify • Apple Podcasts",
             fill=(110, 110, 110), font=subtitle_font, anchor="mm")

    # Optional: Simple QR code placeholder (can be added later)
    # For now, just a decorative element
    qr_y = 1400
    qr_size = 200
    qr_bbox = [
        width // 2 - qr_size // 2,
        qr_y - qr_size // 2,
        width // 2 + qr_size // 2,
        qr_y + qr_size // 2
    ]
    draw.rectangle(qr_bbox, outline=accent_color, width=4)
    draw.text((width // 2, qr_y), "QR",
             fill=accent_color, font=subtitle_font, anchor="mm")

    # Save
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, quality=95)

    return output_path


def main():
    """Test card generation"""
    import sys

    output_dir = Path("./shorts/cards_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Test intro cards for each chapter
    test_chapters = [
        (1, "Intro", 7),
        (2, "How Distillation Works", 7),
        (3, "The Pricing War", 7),
        (4, "Micro-Distillation for Solopreneurs", 7),
        (5, "Non-Technical Operator Framework", 7),
        (6, "Operational Portability Strategy", 7),
        (7, "Recap", 7),
    ]

    print("Generating test cards...\n")

    for num, title, total in test_chapters:
        intro_path = output_dir / f"intro-{num:02d}-{title.lower().replace(' ', '-')}.png"
        create_intro_card(num, title, total, intro_path)
        print(f"✓ Created: {intro_path.name}")

    # Test outro card
    outro_path = output_dir / "outro.png"
    create_outro_card(outro_path)
    print(f"✓ Created: {outro_path.name}")

    print(f"\nAll cards saved to: {output_dir}")


if __name__ == "__main__":
    main()
