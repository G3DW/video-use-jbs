#!/usr/bin/env python3
"""
Regenerate Dialogue — end-to-end orchestrator for turning a raw two-speaker
NotebookLM-style episode into a mastered narration track voiced by ElevenLabs,
with Joe's cloned voice always on the correct (male) speaker regardless of
which speaker NotebookLM happened to diarize first that day.

Chains:
  1. helpers/transcribe.py   — diarized Scribe transcription of the raw audio
  2. detect_speaker_gender.py — pitch-classifies speaker_0/speaker_1 as male/female
  3. voice_dialogue.py        — regenerates the dialogue via ElevenLabs (eleven_v3,
                                 emotion tags, mastering chain) with the correct
                                 --male-speaker/--female-speaker assignment

Usage:
  python3 regenerate_dialogue.py \
      --audio path/to/raw_episode.m4a \
      --out-dir path/to/edit/dialogue \
      --output path/to/edit/final_narration.mp3
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def load_api_key():
    """voice_dialogue.py reads ELEVENLABS_API_KEY from the environment only
    (no .env fallback), so load it here and inject it into the subprocess env."""
    if os.environ.get("ELEVENLABS_API_KEY"):
        return os.environ["ELEVENLABS_API_KEY"]
    for candidate in [SCRIPT_DIR / ".env",
                       Path("/Users/joey_makes_stuff/Documents/GitHub/video-use/.env")]:
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
    sys.exit("[error] ELEVENLABS_API_KEY not found in environment or .env")

DEFAULT_MALE_VOICE_ID = "8579yP6p1e1Pydb8F0dg"    # Digital Joey Voice (cloned)
DEFAULT_FEMALE_VOICE_ID = "OYTbf65OHHFELVut7v2H"  # Hope - natural conversations

TRANSCRIBE_SCRIPT = Path("/Users/joey_makes_stuff/Documents/GitHub/video-use/helpers/transcribe.py")
VENV_PYTHON = Path("/Users/joey_makes_stuff/Documents/GitHub/video-use/.venv/bin/python")


def run(cmd, **kwargs):
    print(f"[run] {' '.join(str(c) for c in cmd)}", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(f"[error] command failed: {' '.join(str(c) for c in cmd)}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Regenerate a diarized dialogue episode with ElevenLabs voices")
    parser.add_argument("--audio", required=True, help="Path to raw NotebookLM-style episode audio")
    parser.add_argument("--out-dir", required=True, help="Working directory for batch mp3s / intermediates")
    parser.add_argument("--output", required=True, help="Final mastered narration mp3 path")
    parser.add_argument("--male-voice-id", default=DEFAULT_MALE_VOICE_ID)
    parser.add_argument("--female-voice-id", default=DEFAULT_FEMALE_VOICE_ID)
    parser.add_argument("--model-id", default="eleven_v3")
    parser.add_argument("--speed", type=float, default=1.1)
    parser.add_argument("--transcript", default=None,
                         help="Reuse an already-transcribed (optionally humanized) transcript JSON "
                              "instead of re-transcribing the raw audio. Stage 1 already produces this "
                              "at edit/source_transcript/transcripts/<stem>.json (run through "
                              "humanize_transcript.py) — pass it here to skip the redundant Scribe call.")
    parser.add_argument("--speaker-map", default=None,
                         help="Reuse an already-computed speaker_map.json instead of re-running pitch "
                              "detection. Pairs with --transcript — both come from the same Stage 1 run.")
    args = parser.parse_args()

    audio_path = Path(args.audio).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.transcript:
        # Reuse Stage 1's transcript (humanized or raw) instead of re-transcribing.
        transcript_json = Path(args.transcript).resolve()
        if not transcript_json.exists():
            sys.exit(f"[error] --transcript path not found: {transcript_json}")
        print(f"[1/3] Reusing existing transcript: {transcript_json}", file=sys.stderr)
    else:
        # 1. Transcribe raw source (diarized, word-level, audio events)
        print("[1/3] Transcribing raw episode audio...", file=sys.stderr)
        transcribe_edit_dir = out_dir / "source_transcript"
        run([str(VENV_PYTHON), str(TRANSCRIBE_SCRIPT), str(audio_path),
             "--edit-dir", str(transcribe_edit_dir), "--num-speakers", "2"])
        transcript_json = transcribe_edit_dir / "transcripts" / f"{audio_path.stem}.json"
        if not transcript_json.exists():
            sys.exit(f"[error] expected transcript not found: {transcript_json}")

    if args.speaker_map:
        speaker_map_path = Path(args.speaker_map).resolve()
        if not speaker_map_path.exists():
            sys.exit(f"[error] --speaker-map path not found: {speaker_map_path}")
        print(f"[2/3] Reusing existing speaker map: {speaker_map_path}", file=sys.stderr)
    else:
        # 2. Detect which diarized speaker is male vs female
        print("[2/3] Detecting speaker gender via pitch analysis...", file=sys.stderr)
        speaker_map_path = out_dir / "speaker_map.json"
        run([str(VENV_PYTHON), str(SCRIPT_DIR / "detect_speaker_gender.py"),
             "--transcript", str(transcript_json), "--audio", str(audio_path),
             "--output", str(speaker_map_path)])
    speaker_map = json.loads(speaker_map_path.read_text())
    male_speaker = speaker_map["male_speaker"]
    female_speaker = speaker_map["female_speaker"]
    print(f"[info] {male_speaker} -> male ({speaker_map['male_f0_hz']} Hz), "
          f"{female_speaker} -> female ({speaker_map['female_f0_hz']} Hz)", file=sys.stderr)

    # 3. Regenerate dialogue via ElevenLabs with the correct speaker assignment
    print("[3/3] Regenerating dialogue via ElevenLabs...", file=sys.stderr)
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dialogue_env = {**os.environ, "ELEVENLABS_API_KEY": load_api_key()}
    run([str(VENV_PYTHON), str(SCRIPT_DIR / "voice_dialogue.py"),
         "--transcript", str(transcript_json),
         "--male-voice-id", args.male_voice_id,
         "--female-voice-id", args.female_voice_id,
         "--male-speaker", male_speaker,
         "--female-speaker", female_speaker,
         "--out-dir", str(out_dir / "batches"),
         "--output", str(output_path),
         "--model-id", args.model_id,
         "--speed", str(args.speed)],
        timeout=900, env=dialogue_env)

    print(f"[done] mastered narration -> {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
