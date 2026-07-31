#!/usr/bin/env python3
"""
Build All Shorts - Convenience script to extract and render all short-form videos
"""

import json
import sys
from pathlib import Path
import subprocess


def parse_chapters_from_youtube_info(youtube_info_path):
    """Parse chapter timestamps from youtube-info.md"""
    chapters = []

    with open(youtube_info_path) as f:
        in_chapters = False
        for line in f:
            line = line.strip()

            if "## Chapter Timestamps" in line or "Chapter Timestamps" in line:
                in_chapters = True
                continue

            if in_chapters:
                if line.startswith("```") and chapters:
                    # End of chapters block
                    break

                if line and not line.startswith("```") and not line.startswith("#"):
                    # Parse timestamp line: "00:00 - Intro"
                    if " - " in line:
                        time_part, title = line.split(" - ", 1)
                        time_part = time_part.strip()

                        # Parse MM:SS
                        parts = time_part.split(":")
                        if len(parts) == 2:
                            mins, secs = parts
                            total_seconds = int(mins) * 60 + int(secs)
                            chapters.append([total_seconds, title.strip()])

    return chapters


def main():
    if len(sys.argv) < 4:
        print("Usage: build_all_shorts.py <transcript.json> <youtube-info.md> <audio.mp3> [output_dir]")
        print("\nThis script will:")
        print("  1. Parse chapters from youtube-info.md")
        print("  2. Extract audio and transcript segments")
        print("  3. Render all short-form videos")
        sys.exit(1)

    transcript_json = Path(sys.argv[1])
    youtube_info = Path(sys.argv[2])
    audio_file = Path(sys.argv[3])
    output_dir = Path(sys.argv[4]) if len(sys.argv) > 4 else Path("./shorts/final")

    script_dir = Path(__file__).parent

    print("\n" + "="*60)
    print("SHORT-FORM CONTENT BUILDER")
    print("="*60 + "\n")

    # Validate inputs
    if not transcript_json.exists():
        print(f"✗ Transcript not found: {transcript_json}")
        sys.exit(1)

    if not youtube_info.exists():
        print(f"✗ YouTube info not found: {youtube_info}")
        sys.exit(1)

    if not audio_file.exists():
        print(f"✗ Audio file not found: {audio_file}")
        sys.exit(1)

    print(f"Transcript: {transcript_json}")
    print(f"Chapters: {youtube_info}")
    print(f"Audio: {audio_file}")
    print(f"Output: {output_dir}\n")

    # Parse chapters
    print("1. Parsing chapters...")
    chapters = parse_chapters_from_youtube_info(youtube_info)

    if not chapters:
        print("✗ No chapters found in youtube-info.md")
        sys.exit(1)

    print(f"   Found {len(chapters)} chapters")
    for i, (ts, title) in enumerate(chapters, 1):
        mins = ts // 60
        secs = ts % 60
        print(f"     {i}. [{mins:02d}:{secs:02d}] {title}")

    # Save chapters JSON for extraction script
    chapters_json = Path("./shorts/chapters_temp.json")
    chapters_json.parent.mkdir(exist_ok=True)
    with open(chapters_json, 'w') as f:
        json.dump(chapters, f)

    # Extract chapters
    print("\n2. Extracting chapter segments...")
    extracted_dir = Path("./shorts/extracted")

    extract_script = script_dir / "extract_chapters.py"
    result = subprocess.run([
        "python3", str(extract_script),
        str(audio_file),
        str(transcript_json),
        str(chapters_json),
        str(extracted_dir)
    ])

    if result.returncode != 0:
        print("✗ Chapter extraction failed")
        sys.exit(1)

    # Render shorts
    print("\n3. Rendering short-form videos...")
    render_script = script_dir / "render_shorts.py"
    chapters_index = extracted_dir / "chapters_index.json"

    result = subprocess.run([
        "python3", str(render_script),
        str(chapters_index),
        str(output_dir)
    ])

    if result.returncode != 0:
        print("✗ Rendering failed")
        sys.exit(1)

    # Summary
    print("\n" + "="*60)
    print("✓ SHORT-FORM CONTENT READY!")
    print("="*60 + "\n")
    print(f"Output directory: {output_dir}")
    print(f"\nGenerated {len(chapters)} vertical videos (1080×1920)")
    print("\nReady to upload to:")
    print("  • Instagram Reels")
    print("  • TikTok")
    print("  • YouTube Shorts")
    print("  • Facebook/LinkedIn\n")


if __name__ == "__main__":
    main()
