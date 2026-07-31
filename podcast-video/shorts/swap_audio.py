#!/usr/bin/env python3
"""
Swap Blotato's AI-synthesized voiceover for the original podcast audio.

Blotato's "AI Video with AI Voice" template always narrates with an
ElevenLabs voice — it does not, and cannot, use your own audio. This script
takes the AI-generated video (visuals + captions we want to keep) and the
original chapter audio (.m4a) and produces a final video with the real
voice, time-scaling the video so its duration matches the real audio.

Usage:
  swap_audio.py <ai_generated.mp4> <original_chapter.m4a> <final.mp4>
"""

import subprocess
import sys
from pathlib import Path


def probe_duration(path: str) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ])
    return float(out.decode().strip())


def swap_audio(video_file: str, audio_file: str, output_file: str) -> Path:
    video_duration = probe_duration(video_file)
    audio_duration = probe_duration(audio_file)
    drift = video_duration - audio_duration
    ratio = video_duration / audio_duration if audio_duration else 1.0

    print(f"Video duration: {video_duration:.2f}s")
    print(f"Audio duration: {audio_duration:.2f}s")
    print(f"Drift: {drift:+.2f}s ({'video slower' if drift > 0 else 'video faster'})")
    if abs(drift) > 1.0:
        print(f"⚠ Drift exceeds 1s — scenes may visibly desync from narration.")
        print(f"  Consider the Image Slideshow + local compositing fallback instead.")

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Retime the video stream to match the real audio's duration, then mux
    # the real audio in. setpts scales presentation timestamps: ratio > 1
    # means the AI video runs long relative to the real audio, so we speed
    # video playback up (divide PTS) to compress it to match.
    pts_factor = 1.0 / ratio if ratio else 1.0

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_file),
        "-i", str(audio_file),
        "-filter:v", f"setpts={pts_factor:.6f}*PTS",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(output_path),
    ]
    print(f"\nRunning: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    final_duration = probe_duration(str(output_path))
    print(f"\n✓ Saved: {output_path}")
    print(f"  Final duration: {final_duration:.2f}s (target audio: {audio_duration:.2f}s)")

    return output_path


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: swap_audio.py <ai_generated.mp4> <original_chapter.m4a> <final.mp4>")
        sys.exit(1)

    swap_audio(sys.argv[1], sys.argv[2], sys.argv[3])
