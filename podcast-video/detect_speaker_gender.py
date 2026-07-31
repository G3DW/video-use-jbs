#!/usr/bin/env python3
"""
Detect Speaker Gender — pitch-analyzes each diarized speaker in a Scribe
transcript to determine which speaker_id is male vs. female, so the correct
ElevenLabs voice ID can be assigned regardless of which speaker NotebookLM
happened to put first that day.

Input: a Scribe transcript JSON (word-level, with speaker_id per word, as
produced by helpers/transcribe.py) and the source audio it was transcribed
from. Output: a JSON mapping of male_speaker/female_speaker + the median
fundamental frequency (F0) measured for each, printed to stdout and
optionally written to a file.

Usage:
  python3 detect_speaker_gender.py \
      --transcript path/to/transcript.json \
      --audio path/to/source.mp3 \
      --output speaker_map.json
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import librosa

MIN_GAP_TO_SPLIT = 1.0   # seconds; words closer than this stay in one segment
MAX_SECONDS_PER_SPEAKER = 10.0  # cap audio sampled per speaker for speed


def build_segments(words, speaker_id):
    """Merge a speaker's word timestamps into contiguous audio segments."""
    segments = []
    cur_start = None
    cur_end = None
    for w in words:
        if w.get("speaker_id") != speaker_id or w.get("type") != "word":
            continue
        if cur_start is None:
            cur_start, cur_end = w["start"], w["end"]
        elif w["start"] - cur_end <= MIN_GAP_TO_SPLIT:
            cur_end = w["end"]
        else:
            segments.append((cur_start, cur_end))
            cur_start, cur_end = w["start"], w["end"]
    if cur_start is not None:
        segments.append((cur_start, cur_end))
    return segments


def pick_longest(segments, max_seconds):
    """Pick the longest segments up to a total duration cap."""
    ranked = sorted(segments, key=lambda s: s[1] - s[0], reverse=True)
    picked, total = [], 0.0
    for start, end in ranked:
        if total >= max_seconds:
            break
        picked.append((start, end))
        total += end - start
    return picked


def extract_segment(audio_path, start, end, out_path):
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(audio_path),
         "-ss", str(max(0, start)), "-to", str(end),
         "-vn", "-ac", "1", "-ar", "22050",
         str(out_path)],
        check=True, capture_output=True,
    )


def median_f0(audio_path, segments, tmp_dir):
    all_f0 = []
    for i, (start, end) in enumerate(segments):
        clip_path = tmp_dir / f"clip_{i:02d}.wav"
        extract_segment(audio_path, start, end, clip_path)
        y, sr = librosa.load(clip_path, sr=22050, mono=True)
        if len(y) < sr * 0.1:
            continue
        f0, voiced_flag, _ = librosa.pyin(
            y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C6"), sr=sr
        )
        voiced = f0[voiced_flag]
        if len(voiced):
            all_f0.extend(voiced.tolist())
    if not all_f0:
        return None
    return float(np.median(all_f0))


def main():
    parser = argparse.ArgumentParser(description="Classify diarized speakers as male/female via pitch analysis")
    parser.add_argument("--transcript", required=True, help="Path to Scribe transcript JSON")
    parser.add_argument("--audio", required=True, help="Path to the source audio the transcript was made from")
    parser.add_argument("--output", help="Optional path to write the speaker map JSON")
    args = parser.parse_args()

    with open(args.transcript) as f:
        data = json.load(f)

    words = data.get("words", [])
    speaker_ids = sorted({w["speaker_id"] for w in words if w.get("type") == "word" and "speaker_id" in w})

    if len(speaker_ids) != 2:
        sys.exit(f"[error] expected exactly 2 diarized speakers, found {len(speaker_ids)}: {speaker_ids}")

    audio_path = Path(args.audio)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        f0_by_speaker = {}
        for sid in speaker_ids:
            segments = pick_longest(build_segments(words, sid), MAX_SECONDS_PER_SPEAKER)
            if not segments:
                sys.exit(f"[error] no usable audio segments found for {sid}")
            speaker_tmp = tmp_dir / sid
            speaker_tmp.mkdir()
            f0 = median_f0(audio_path, segments, speaker_tmp)
            if f0 is None:
                sys.exit(f"[error] pitch detection failed for {sid} (no voiced frames)")
            f0_by_speaker[sid] = f0
            print(f"[info] {sid}: median F0 = {f0:.1f} Hz ({len(segments)} segments)", file=sys.stderr)

    male_speaker = min(f0_by_speaker, key=f0_by_speaker.get)
    female_speaker = max(f0_by_speaker, key=f0_by_speaker.get)

    result = {
        "male_speaker": male_speaker,
        "female_speaker": female_speaker,
        "male_f0_hz": round(f0_by_speaker[male_speaker], 1),
        "female_f0_hz": round(f0_by_speaker[female_speaker], 1),
    }

    print(json.dumps(result, indent=2))

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2))
        print(f"[done] speaker map -> {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
