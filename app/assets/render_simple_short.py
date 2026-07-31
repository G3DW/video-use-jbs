#!/usr/bin/env python3
"""Simple short-form video renderer without HyperFrames dependency"""

import json
import subprocess
import sys
from pathlib import Path

def render_simple_short(audio_file, transcript_file, chapter_title, output_path):
    """
    Render a simple vertical short with static subtitles
    
    Args:
        audio_file: Chapter audio segment
        transcript_file: Chapter transcript JSON
        chapter_title: Title for intro card
        output_path: Output video path
    """
    
    # Get audio duration
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_file
    ]
    duration = float(subprocess.check_output(probe_cmd).decode().strip())
    
    print(f"Creating simple short for: {chapter_title}")
    print(f"  Duration: {duration:.1f}s")
    
    temp_dir = Path("./shorts/temp_simple")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Create intro card with PIL
    print("  Creating intro card...")
    from PIL import Image, ImageDraw, ImageFont
    
    img = Image.new('RGB', (1080, 1920), color=(10, 10, 10))
    draw = ImageDraw.Draw(img)
    
    # Purple theme for "How Distillation Works"
    accent_color = (139, 92, 246)
    
    # Top bar
    draw.rectangle([0, 0, 1080, 8], fill=accent_color)
    
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 96, index=1)
        meta_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
    except:
        title_font = ImageFont.load_default()
        meta_font = ImageFont.load_default()
    
    # Brand
    draw.text((540, 200), "Daily AI Pulse", fill=(150, 150, 150), font=meta_font, anchor="mm")
    
    # Chapter indicator
    draw.text((540, 300), "Chapter 2 of 7", fill=(110, 110, 110), font=meta_font, anchor="mm")
    
    # Title
    draw.text((540, 960), chapter_title, fill=(255, 255, 255), font=title_font, anchor="mm")
    
    # Bottom bar
    draw.rectangle([0, 1912, 1080, 1920], fill=accent_color)
    
    intro_card = temp_dir / "intro.png"
    img.save(intro_card, quality=95)
    
    # Convert intro to video (2.5s)
    intro_video = temp_dir / "intro.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(intro_card),
        "-c:v", "libx264", "-t", "2.5", "-pix_fmt", "yuv420p",
        "-r", "30", str(intro_video)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    print("  ✓ Intro card created")
    
    # Create main content with waveform and simple subtitles
    print("  Creating main content...")
    
    # Load transcript for subtitle text
    with open(transcript_file) as f:
        transcript_data = json.load(f)
    
    words = [w for w in transcript_data.get('words', []) if w.get('type') != 'spacing']
    full_text = ' '.join([w.get('text', '').strip() for w in words if w.get('text', '').strip()])
    
    # Create main video with waveform
    main_content = temp_dir / "main.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:d={duration}:r=30",
        "-i", audio_file,
        "-filter_complex",
        f"[1:a]showwaves=s=800x300:mode=line:rate=30:colors=#FFFFFF@0.7[wave];"
        f"[0:v][wave]overlay=(W-w)/2:(H-h)/2[out]",
        "-map", "[out]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        str(main_content)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    print("  ✓ Main content created")
    
    # Create outro card
    print("  Creating outro card...")
    img = Image.new('RGB', (1080, 1920), color=(10, 10, 10))
    draw = ImageDraw.Draw(img)
    
    # Orange accent
    outro_accent = (255, 90, 0)
    
    draw.rectangle([0, 0, 1080, 8], fill=outro_accent)
    draw.rectangle([0, 1912, 1080, 1920], fill=outro_accent)
    
    try:
        cta_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 72, index=1)
        handle_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 96, index=1)
        sub_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 42)
    except:
        cta_font = ImageFont.load_default()
        handle_font = ImageFont.load_default()
        sub_font = ImageFont.load_default()
    
    draw.text((540, 700), "Full Episode Available", fill=(200, 200, 200), font=cta_font, anchor="mm")
    draw.text((540, 960), "@dailyaipulse", fill=(255, 255, 255), font=handle_font, anchor="mm")
    draw.text((540, 1100), "YouTube • Spotify • Apple Podcasts", fill=(110, 110, 110), font=sub_font, anchor="mm")
    
    outro_card = temp_dir / "outro.png"
    img.save(outro_card, quality=95)
    
    # Convert outro to video (3s)
    outro_video = temp_dir / "outro.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(outro_card),
        "-c:v", "libx264", "-t", "3.0", "-pix_fmt", "yuv420p",
        "-r", "30", str(outro_video)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    print("  ✓ Outro card created")
    
    # Concatenate all parts
    print("  Concatenating segments...")
    concat_list = temp_dir / "concat.txt"
    with open(concat_list, 'w') as f:
        f.write(f"file '{intro_video}'\n")
        f.write(f"file '{main_content}'\n")
        f.write(f"file '{outro_video}'\n")
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy",
        str(output_path)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    total_duration = 2.5 + duration + 3.0
    print(f"  ✓ Final video: {output_path.name} ({total_duration:.1f}s)")
    
    return output_path

if __name__ == "__main__":
    audio = "./shorts/extracted_single/02-how-distillation-works-8-56-to-11-41.m4a"
    transcript = "./shorts/extracted_single/02-how-distillation-works-transcript.json"
    title = "How Distillation Works"
    output = "./shorts/final_test/02-how-distillation-works-SIMPLE.mp4"
    
    render_simple_short(audio, transcript, title, output)
    print("\n✓ Done!")
