#!/usr/bin/env python3
"""
Prepare Scenes for AI-Generated Short
Step 1 of 2: transcript -> segmented scenes.json (visual_prompt left blank)

This does NOT call any LLM API (no anthropic dependency, no extra billing).
The visual_prompt for each scene is meant to be filled in by whoever is
driving this (e.g. Claude Code, in-session) by editing the output JSON,
then handed to submit_short.py.

Usage:
  prepare_scenes.py <transcript.json> <chapter_title> <out_scenes.json> [visual_style]
"""

import json
import sys
from pathlib import Path
from ai_scene_generator import AISceneGenerator, MAX_SCENES


def prepare_scenes(transcript_file: str, chapter_title: str, output_file: str,
                    visual_style: str = "cinematic technical") -> Path:
    print("=" * 60)
    print("PREPARE SCENES")
    print("=" * 60)

    print(f"\n[1/2] Loading transcript: {Path(transcript_file).name}")
    with open(transcript_file) as f:
        transcript_data = json.load(f)

    print(f"\n[2/2] Segmenting into scenes (max {MAX_SCENES})...")
    generator = AISceneGenerator.__new__(AISceneGenerator)  # skip API-key check, no network needed here
    scenes = generator.segment_transcript_into_scenes(transcript_data, max_scene_duration=8.0)

    if not scenes:
        raise ValueError("No words found in transcript; nothing to segment")

    total_duration = scenes[-1]['end'] - scenes[0]['start']
    covered = sum(s['duration'] for s in scenes)

    print(f"  ✓ {len(scenes)} scenes (limit {MAX_SCENES})")
    print(f"  ✓ Coverage: {covered:.1f}s of {total_duration:.1f}s chapter span")
    if len(scenes) >= MAX_SCENES:
        print(f"  (scenes were merged down to fit the {MAX_SCENES}-scene cap)")

    for i, scene in enumerate(scenes):
        print(f"    {i+1:2d}. {scene['duration']:5.1f}s: \"{scene['text'][:70]}\"")

    out = {
        "chapter_title": chapter_title,
        "visual_style": visual_style,
        "scenes": [
            {
                "start": s["start"],
                "end": s["end"],
                "duration": s["duration"],
                "text": s["text"],
                "visual_prompt": "",  # <-- fill this in before running submit_short.py
            }
            for s in scenes
        ],
    }

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(out, f, indent=2)

    print(f"\n✓ Wrote {output_path}")
    print(f"\nNext step: fill in each scene's \"visual_prompt\" field (style: {visual_style!r}),")
    print(f"then run: submit_short.py {output_path} <output.mp4>")

    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: prepare_scenes.py <transcript.json> <chapter_title> <out_scenes.json> [visual_style]")
        sys.exit(1)

    transcript = sys.argv[1]
    title = sys.argv[2]
    output = sys.argv[3]
    style = sys.argv[4] if len(sys.argv) > 4 else "cinematic technical"

    prepare_scenes(transcript, title, output, style)
