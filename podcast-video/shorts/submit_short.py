#!/usr/bin/env python3
"""
Submit AI-Generated Short to Blotato
Step 2 of 2: scenes.json (with visual_prompt filled in) -> Blotato job -> download

Usage:
  submit_short.py <scenes.json> <output.mp4> [--model MODEL] [--no-animate]
                   [--aspect 9:16] [--voice "Brian (American, deep)"]
                   [--no-voiceover] [--timeout 1800]
"""

import argparse
import json
import sys
from pathlib import Path
from ai_scene_generator import AISceneGenerator, VALID_AI_IMAGE_MODELS


def submit_short(scenes_file: str, output_file: str, ai_image_model: str,
                  animate_images: bool, aspect_ratio: str, voice_name: str,
                  enable_voiceover: bool, timeout: int) -> Path:
    print("=" * 60)
    print("SUBMIT AI-GENERATED SHORT")
    print("=" * 60)

    print(f"\n[1/4] Loading scenes: {Path(scenes_file).name}")
    with open(scenes_file) as f:
        data = json.load(f)

    chapter_title = data.get("chapter_title", "AI Generated Short")
    scenes = data["scenes"]

    missing = [i + 1 for i, s in enumerate(scenes) if not s.get("visual_prompt", "").strip()]
    if missing:
        print(f"\n✗ {len(missing)} scene(s) are missing visual_prompt: {missing}")
        print(f"  Edit {scenes_file} and fill in every visual_prompt field before submitting.")
        sys.exit(1)

    print(f"  ✓ {len(scenes)} scenes, all have visual prompts")

    print(f"\n[2/4] Initializing Blotato API...")
    generator = AISceneGenerator()

    print(f"\n[3/4] Submitting to Blotato...")
    item = generator.create_video(
        scenes,
        ai_image_model=ai_image_model,
        animate_images=animate_images,
        aspect_ratio=aspect_ratio,
        title=f"{chapter_title} - AI Generated",
        enable_voiceover=enable_voiceover,
        voice_name=voice_name,
    )

    creation_id = item.get('id')
    if not creation_id:
        raise RuntimeError(f"No id in response: {item}")
    print(f"  ✓ Job submitted: {creation_id}")

    print(f"\n[4/4] Polling status (max {timeout // 60} minutes)...")
    result = generator.poll_status(creation_id, timeout=timeout)

    media_url = result.get('mediaUrl')
    if not media_url:
        raise RuntimeError(f"No mediaUrl in response: {result}")

    output_path = generator.download_video(media_url, Path(output_file))

    print(f"\n{'='*60}")
    print(f"✓ AI-GENERATED SHORT COMPLETE!")
    print(f"{'='*60}")
    print(f"\nOutput: {output_path}")
    print(f"\nNote: this video has an AI-synthesized ({voice_name}) voiceover,")
    print(f"not the original podcast audio. Run swap_audio.py to restore the")
    print(f"real voice if that's what you want for publishing.")

    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenes_file")
    parser.add_argument("output_file")
    parser.add_argument("--model", default="replicate/black-forest-labs/flux-1.1-pro",
                         choices=VALID_AI_IMAGE_MODELS)
    parser.add_argument("--no-animate", action="store_true")
    parser.add_argument("--aspect", default="9:16")
    parser.add_argument("--voice", default="Brian (American, deep)")
    parser.add_argument("--no-voiceover", action="store_true")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    submit_short(
        args.scenes_file,
        args.output_file,
        ai_image_model=args.model,
        animate_images=not args.no_animate,
        aspect_ratio=args.aspect,
        voice_name=args.voice,
        enable_voiceover=not args.no_voiceover,
        timeout=args.timeout,
    )
