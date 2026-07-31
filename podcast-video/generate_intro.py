#!/usr/bin/env python3
"""
Generate Intro — synthesizes a short spoken intro via ElevenLabs single-voice
TTS (eleven_v3, supports inline audio/emotion tags like [excited]/[curious]),
then runs the same podcast mastering chain used by voice_dialogue.py
(compression, EQ, de-ess, two-pass loudness normalization).

Input is a plain text file with the intro script (eleven_v3 tags allowed
inline). Output is a single mastered mp3 ready to prepend to the episode
audio in build_video.py.

Usage:
  python3 generate_intro.py \
      --text-file intro.txt \
      --voice-id 8579yP6p1e1Pydb8F0dg \
      --output edit/temp/intro.mp3
"""

import argparse
import json
import os
import sys
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def load_api_key():
    script_dir = Path(__file__).resolve().parent
    candidates = [script_dir / ".env", Path(".env")]

    config_path = script_dir / "config.json"
    if config_path.exists():
        video_use_repo = json.loads(config_path.read_text()).get("paths", {}).get("video_use_repo")
        if video_use_repo:
            candidates.insert(1, Path(video_use_repo) / ".env")

    for candidate in candidates:
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == "ELEVENLABS_API_KEY":
                    v = v.strip().strip('"').strip("'")
                    if v:
                        return v
    v = os.environ.get("ELEVENLABS_API_KEY", "")
    if not v:
        sys.exit("[error] ELEVENLABS_API_KEY not found in .env or environment")
    return v


def synthesize(text, voice_id, api_key, model_id, stability, timeout):
    url = TTS_URL.format(voice_id=voice_id)
    body = json.dumps({
        "text": text,
        "model_id": model_id,
        "voice_settings": {"stability": stability},
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    print(f"[info] synthesizing intro ({len(text)} chars)...", file=sys.stderr)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        print(f"[error] TTS FAILED {e.code} {e.read().decode()}", file=sys.stderr)
        raise


def master(raw_path, output_path, loudness_i, loudness_tp, loudness_lra):
    chain = (
        "highpass=f=90,"
        "acompressor=threshold=-18dB:ratio=3:attack=5:release=60:makeup=2,"
        "equalizer=f=3200:t=q:w=1.2:g=2.5,"
        "deesser=i=0.15,"
        f"loudnorm=I={loudness_i}:TP={loudness_tp}:LRA={loudness_lra}:print_format=json"
    )
    measure = subprocess.run(
        ["ffmpeg", "-y", "-i", str(raw_path), "-af", chain, "-f", "null", "-"],
        check=True, capture_output=True, text=True,
    )
    stderr = measure.stderr
    json_start = stderr.rfind("{")
    stats = json.loads(stderr[json_start:stderr.rfind("}") + 1])

    chain2 = (
        "highpass=f=90,"
        "acompressor=threshold=-18dB:ratio=3:attack=5:release=60:makeup=2,"
        "equalizer=f=3200:t=q:w=1.2:g=2.5,"
        "deesser=i=0.15,"
        f"loudnorm=I={loudness_i}:TP={loudness_tp}:LRA={loudness_lra}:"
        f"measured_I={stats['input_i']}:measured_TP={stats['input_tp']}:"
        f"measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}:"
        f"offset={stats['target_offset']}:linear=true"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(raw_path), "-af", chain2, "-ar", "44100", str(output_path)],
        check=True, capture_output=True,
    )


def main():
    parser = argparse.ArgumentParser(description="Generate a spoken podcast intro via ElevenLabs")
    parser.add_argument("--text-file", required=True, help="Path to intro script text (eleven_v3 tags allowed)")
    parser.add_argument("--voice-id", default="8579yP6p1e1Pydb8F0dg", help="ElevenLabs voice ID (default: Digital Joey Voice)")
    parser.add_argument("--model-id", default="eleven_v3")
    parser.add_argument("--stability", type=float, default=0.3)
    parser.add_argument("--output", required=True, help="Final mastered mp3 path")
    parser.add_argument("--no-master", action="store_true", help="Skip the mastering chain")
    parser.add_argument("--loudness-i", default="-16", help="Target integrated loudness (LUFS)")
    parser.add_argument("--loudness-tp", default="-1.5", help="Target true peak (dBTP)")
    parser.add_argument("--loudness-lra", default="11", help="Target loudness range (LU)")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    api_key = load_api_key()
    text = Path(args.text_file).read_text().strip()
    if not text:
        sys.exit(f"[error] {args.text_file} is empty")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    audio = synthesize(text, args.voice_id, api_key, args.model_id, args.stability, args.timeout)

    if args.no_master:
        output_path.write_bytes(audio)
        print(f"[done] intro -> {output_path}", file=sys.stderr)
        return

    raw_path = output_path.parent / f"{output_path.stem}_raw.mp3"
    raw_path.write_bytes(audio)
    master(raw_path, output_path, args.loudness_i, args.loudness_tp, args.loudness_lra)
    print(f"[done] mastered intro -> {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
