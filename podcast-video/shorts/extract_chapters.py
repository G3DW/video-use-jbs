#!/usr/bin/env python3
"""
Chapter Extraction - Extract audio and transcript segments for each chapter
"""

import json
import subprocess
import sys
from pathlib import Path


def extract_audio_segment(input_audio, start_time, end_time, output_path):
    """Extract audio segment using FFmpeg"""
    duration = end_time - start_time

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_audio),
        "-ss", str(start_time),
        "-t", str(duration),
        "-c:a", "aac",
        "-b:a", "192k",
        str(output_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"✗ Failed to extract audio: {result.stderr}")
        return False

    return True


def extract_transcript_segment(words, start_time, end_time):
    """Extract word-level transcript for time range"""
    segment_words = []

    for word in words:
        word_start = word.get('start', 0)
        word_end = word.get('end', 0)

        # Include word if it overlaps with our segment
        if word_start < end_time and word_end > start_time:
            # Adjust timestamps relative to segment start
            adjusted_word = word.copy()
            adjusted_word['start'] = max(0, word_start - start_time)
            adjusted_word['end'] = min(end_time - start_time, word_end - start_time)
            segment_words.append(adjusted_word)

    return segment_words


def extract_chapters(audio_path, transcript_path, chapters, output_dir):
    """
    Extract audio and transcript for each chapter

    Args:
        audio_path: Path to source audio file
        transcript_path: Path to transcript JSON with word-level timing
        chapters: List of (timestamp, title) tuples
        output_dir: Directory to save extracted chapters

    Returns:
        List of chapter info dicts
    """
    audio_path = Path(audio_path)
    transcript_path = Path(transcript_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load transcript
    with open(transcript_path) as f:
        transcript_data = json.load(f)

    words = transcript_data.get('words', [])
    total_duration = words[-1]['end'] if words else 0

    # Process each chapter
    chapter_info = []

    for i, (start_ts, title) in enumerate(chapters):
        # Determine end time (start of next chapter or end of audio)
        if i < len(chapters) - 1:
            end_ts = chapters[i + 1][0]
        else:
            end_ts = total_duration

        duration = end_ts - start_ts

        # Skip very short chapters (< 10 seconds)
        if duration < 10:
            print(f"⊘ Skipping chapter {i+1}: too short ({duration:.1f}s)")
            continue

        # Create chapter slug
        slug = title.lower().replace(' ', '-').replace('/', '-')
        slug = ''.join(c for c in slug if c.isalnum() or c == '-')

        # Format timestamps for filename
        start_str = f"{int(start_ts//60)}-{int(start_ts%60):02d}"
        end_str = f"{int(end_ts//60)}-{int(end_ts%60):02d}"

        # Output paths
        audio_out = output_dir / f"{i+1:02d}-{slug}-{start_str}-to-{end_str}.m4a"
        transcript_out = output_dir / f"{i+1:02d}-{slug}-transcript.json"

        print(f"  Extracting chapter {i+1}/{len(chapters)}: {title}")
        print(f"    Time: {start_str.replace('-', ':')} → {end_str.replace('-', ':')} ({duration:.1f}s)")

        # Extract audio
        if extract_audio_segment(audio_path, start_ts, end_ts, audio_out):
            print(f"    ✓ Audio: {audio_out.name}")
        else:
            continue

        # Extract transcript segment
        segment_words = extract_transcript_segment(words, start_ts, end_ts)

        segment_data = {
            "chapter_number": i + 1,
            "title": title,
            "start_time": start_ts,
            "end_time": end_ts,
            "duration": duration,
            "words": segment_words,
            "word_count": len([w for w in segment_words if w.get('type') != 'spacing'])
        }

        with open(transcript_out, 'w') as f:
            json.dump(segment_data, f, indent=2)

        print(f"    ✓ Transcript: {transcript_out.name} ({segment_data['word_count']} words)")

        chapter_info.append({
            "number": i + 1,
            "title": title,
            "slug": slug,
            "start_time": start_ts,
            "end_time": end_ts,
            "duration": duration,
            "audio_file": str(audio_out),
            "transcript_file": str(transcript_out),
            "filename_base": f"{i+1:02d}-{slug}-{start_str}-to-{end_str}"
        })

    # Save chapter index
    index_path = output_dir / "chapters_index.json"
    with open(index_path, 'w') as f:
        json.dump(chapter_info, f, indent=2)

    print(f"\n✓ Extracted {len(chapter_info)} chapters")
    print(f"✓ Saved index: {index_path}")

    return chapter_info


def main():
    if len(sys.argv) < 4:
        print("Usage: extract_chapters.py <audio> <transcript.json> <chapters.json> [output_dir]")
        print("\nchapters.json format:")
        print('[')
        print('  [0, "Intro"],')
        print('  [536, "How It Works"],')
        print('  ...')
        print(']')
        sys.exit(1)

    audio_path = sys.argv[1]
    transcript_path = sys.argv[2]
    chapters_path = sys.argv[3]
    output_dir = sys.argv[4] if len(sys.argv) > 4 else "./shorts/extracted"

    # Load chapters
    with open(chapters_path) as f:
        chapters = json.load(f)

    print(f"\n{'='*60}")
    print("CHAPTER EXTRACTION")
    print(f"{'='*60}\n")
    print(f"Source audio: {audio_path}")
    print(f"Transcript: {transcript_path}")
    print(f"Chapters: {len(chapters)}")
    print(f"Output: {output_dir}\n")

    extract_chapters(audio_path, transcript_path, chapters, output_dir)


if __name__ == "__main__":
    main()
