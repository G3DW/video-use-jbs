#!/usr/bin/env python3
"""Simple short-form video renderer - Fixed audio handling"""

import json
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def create_card_with_audio(card_image, duration, output_video):
    """Convert static card to video with silent audio track"""
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(card_image),
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
        "-c:v", "libx264", "-t", str(duration),
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-r", "30",
        "-shortest",
        str(output_video)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def render_simple_short(audio_file, chapter_title, output_path):
    """Render vertical short with cards and waveform"""
    
    # Get audio duration
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_file
    ]
    duration = float(subprocess.check_output(probe_cmd).decode().strip())
    
    print(f"\nCreating simple short: {chapter_title}")
    print(f"  Duration: {duration:.1f}s")
    
    temp_dir = Path("./shorts/temp_simple_v2")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Create intro card
    print("  Creating intro card...")
    img = Image.new('RGB', (1080, 1920), color=(10, 10, 10))
    draw = ImageDraw.Draw(img)
    
    accent_color = (139, 92, 246)  # Purple
    draw.rectangle([0, 0, 1080, 8], fill=accent_color)
    
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 80, index=1)
        meta_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
    except:
        title_font = ImageFont.load_default()
        meta_font = ImageFont.load_default()
    
    draw.text((540, 200), "Daily AI Pulse", fill=(150, 150, 150), font=meta_font, anchor="mm")
    draw.text((540, 300), "Chapter 2 of 7", fill=(110, 110, 110), font=meta_font, anchor="mm")
    draw.text((540, 960), chapter_title, fill=(255, 255, 255), font=title_font, anchor="mm")
    draw.rectangle([0, 1912, 1080, 1920], fill=accent_color)
    
    intro_card = temp_dir / "intro.png"
    img.save(intro_card, quality=95)
    
    intro_video = temp_dir / "intro.mp4"
    create_card_with_audio(intro_card, 2.5, intro_video)
    print("  ✓ Intro: 2.5s")
    
    # Create main content
    print("  Creating main content with waveform...")
    main_content = temp_dir / "main.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:d={duration}:r=30",
        "-i", audio_file,
        "-filter_complex",
        "[1:a]showwaves=s=900x350:mode=line:rate=30:colors=#FFFFFF@0.8[wave];"
        "[0:v][wave]overlay=(W-w)/2:(H-h)/2[out]",
        "-map", "[out]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        str(main_content)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print(f"  ✓ Main: {duration:.1f}s")
    
    # Create outro card
    print("  Creating outro card...")
    img = Image.new('RGB', (1080, 1920), color=(10, 10, 10))
    draw = ImageDraw.Draw(img)
    
    outro_accent = (255, 90, 0)  # Orange
    draw.rectangle([0, 0, 1080, 8], fill=outro_accent)
    draw.rectangle([0, 1912, 1080, 1920], fill=outro_accent)
    
    try:
        cta_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 72, index=1)
        handle_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 96, index=1)
        sub_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 42)
    except:
        cta_font = handle_font = sub_font = ImageFont.load_default()
    
    draw.text((540, 700), "Full Episode Available", fill=(200, 200, 200), font=cta_font, anchor="mm")
    draw.text((540, 960), "@dailyaipulse", fill=(255, 255, 255), font=handle_font, anchor="mm")
    draw.text((540, 1100), "YouTube • Spotify • Apple", fill=(110, 110, 110), font=sub_font, anchor="mm")
    
    outro_card = temp_dir / "outro.png"
    img.save(outro_card, quality=95)
    
    outro_video = temp_dir / "outro.mp4"
    create_card_with_audio(outro_card, 3.0, outro_video)
    print("  ✓ Outro: 3.0s")
    
    # Concatenate
    print("  Concatenating segments...")
    concat_list = temp_dir / "concat.txt"
    with open(concat_list, 'w') as f:
        f.write(f"file '{intro_video.absolute()}'\n")
        f.write(f"file '{main_content.absolute()}'\n")
        f.write(f"file '{outro_video.absolute()}'\n")
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy",
        str(output_path)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    total = 2.5 + duration + 3.0
    print(f"  ✓ Final: {output_path.name} ({total:.1f}s)")
    print(f"\n✓ Complete! Output: {output_path}")
    
    return output_path

if __name__ == "__main__":
    audio = "./shorts/extracted_single/02-how-distillation-works-8-56-to-11-41.m4a"
    title = "How Distillation Works"
    output = "./shorts/final_test/02-how-distillation-works.mp4"
    
    render_simple_short(audio, title, output)
