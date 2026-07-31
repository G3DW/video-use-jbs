#!/usr/bin/env python3
"""
Voice Dialogue Builder — regenerates a diarized transcript through ElevenLabs
text-to-dialogue (eleven_v3) with per-speaker voice IDs, then runs a podcast
mastering chain (compression, EQ, de-ess, two-pass loudness normalization).

Input is a Scribe transcript JSON (with speaker_id/audio_event words, as
produced by helpers/transcribe.py). Output is a single mastered mp3 ready to
feed into build_video.py in place of the original recording.

Usage:
  python3 voice_dialogue.py \
      --transcript path/to/transcript.json \
      --male-voice-id 8579yP6p1e1Pydb8F0dg \
      --female-voice-id OYTbf65OHHFELVut7v2H \
      --out-dir path/to/edit/dialogue \
      --output path/to/edit/final_narration.mp3
"""

import argparse
import json
import os
import re
import sys
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

DIALOGUE_URL = "https://api.elevenlabs.io/v1/text-to-dialogue"

AUDIO_EVENT_MAP = {
    "[chuckles]": "[laughs]",
    "[smacks lips]": "[laughs]",
    "[laughs]": "[laughs]",
}

EXCITED_STEMS = [
    "wow", "crazy", "insane", "amaz", "incredib", "huge", "wild", "massive",
    "mind-blowing", "unbelievable", "staggering", "fascinat",
    "critical pivot", "perfect way", "that's wild", "love that",
]
CURIOUS_STARTS = ("wait", "really", "so wait", "what if", "how", "why", "hold on", "are we")
SIGH_STEMS = [
    "maddening", "annoying", "frustrat", "nightmare", "exhausting",
    "the problem is", "unfortunately", "ultimate insult", "graveyard",
    "landmine", "token trap", "terrify", "unoptimized", "racked up", "ghost to",
]

PAUSE_GAP = 1.0       # seconds; gaps >= this get an ellipsis pause marker
CHAR_BUDGET = 1900    # stay under the API's 2000-char-per-request cap
TAG_COOLDOWN = 2      # min turns (per speaker) between heuristic emotion tags


def build_turns(words):
    turns = []
    cur = None
    prev_end = None
    for w in words:
        sp = w["speaker_id"]
        wtype = w["type"]
        text = w["text"]
        if cur is None or cur["speaker"] != sp:
            if cur is not None:
                turns.append(cur)
            cur = {"speaker": sp, "buf": [], "has_event": False}
            prev_end = None
        gap = w["start"] - prev_end if (prev_end is not None and wtype != "spacing") else None
        if wtype == "word":
            if gap is not None and gap >= PAUSE_GAP and cur["buf"]:
                cur["buf"].append(" ...")
            cur["buf"].append(text)
            prev_end = w["end"]
        elif wtype == "spacing":
            cur["buf"].append(text)
        elif wtype == "audio_event":
            tag = AUDIO_EVENT_MAP.get(text, text)
            cur["buf"].append(f" {tag} ")
            cur["has_event"] = True
            prev_end = w["end"]
    if cur is not None:
        turns.append(cur)

    clean_turns = []
    for t in turns:
        raw = "".join(t["buf"])
        text = re.sub(r"\s+", " ", raw).strip()
        text = re.sub(r"\s+([.,!?])", r"\1", text)
        if not text:
            continue
        clean_turns.append({"speaker": t["speaker"], "text": text, "has_event": t["has_event"]})
    return clean_turns


def apply_emotion_tags(clean_turns):
    """Heuristic tagging, balanced per-speaker via an independent cooldown counter
    per speaker (not a shared one) so one speaker's tags don't crowd out the other's."""
    last_tagged_idx = {}
    speaker_turn_counter = {}
    for t in clean_turns:
        sp = t["speaker"]
        speaker_turn_counter[sp] = speaker_turn_counter.get(sp, 0) + 1
        idx = speaker_turn_counter[sp]
        last_tagged_idx.setdefault(sp, -99)

        if t["has_event"]:
            last_tagged_idx[sp] = idx
            continue

        low = t["text"].lower()
        tag = None
        if any(w in low for w in EXCITED_STEMS):
            tag = "[excited]"
        elif "?" in t["text"] and low.startswith(CURIOUS_STARTS):
            tag = "[curious]"
        elif any(w in low for w in SIGH_STEMS) and len(t["text"]) > 20:
            tag = "[sighs]"

        if tag and (idx - last_tagged_idx[sp] >= TAG_COOLDOWN):
            t["text"] = f"{tag} {t['text']}"
            last_tagged_idx[sp] = idx
    return clean_turns


def batch_turns(clean_turns, budget=CHAR_BUDGET):
    batches = []
    cur_batch, cur_len = [], 0
    for t in clean_turns:
        l = len(t["text"])
        if cur_len + l > budget and cur_batch:
            batches.append(cur_batch)
            cur_batch, cur_len = [], 0
        cur_batch.append(t)
        cur_len += l
    if cur_batch:
        batches.append(cur_batch)
    return batches


def generate_batches(batches, voice_map, out_dir, api_key, model_id, stability, timeout):
    out_dir.mkdir(parents=True, exist_ok=True)
    batch_paths = []
    for i, batch in enumerate(batches):
        out_path = out_dir / f"batch_{i:03d}.mp3"
        batch_paths.append(out_path)
        if out_path.exists():
            print(f"[info] batch {i}: skip (exists)", file=sys.stderr)
            continue
        inputs = [{"text": t["text"], "voice_id": voice_map[t["speaker"]]} for t in batch]
        body = json.dumps({
            "inputs": inputs,
            "model_id": model_id,
            "settings": {"stability": stability},
        }).encode("utf-8")
        req = urllib.request.Request(
            DIALOGUE_URL, data=body,
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            method="POST",
        )
        print(f"[info] batch {i}: generating ({sum(len(t['text']) for t in batch)} chars, {len(batch)} turns)...", file=sys.stderr)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                audio = resp.read()
            out_path.write_bytes(audio)
            print(f"[info] batch {i}: OK, {len(audio)} bytes", file=sys.stderr)
        except urllib.error.HTTPError as e:
            print(f"[error] batch {i}: FAILED {e.code} {e.read().decode()}", file=sys.stderr)
            raise
    return batch_paths


def stitch_and_master(batch_paths, out_dir, output_path, speed, master, loudness_i, loudness_tp, loudness_lra):
    concat_list = out_dir / "batch_list.txt"
    concat_list.write_text("".join(f"file '{p.name}'\n" for p in batch_paths))

    raw_path = out_dir / "dialogue_raw.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(raw_path)],
        cwd=str(out_dir), check=True, capture_output=True,
    )

    sped_path = out_dir / "dialogue_sped.mp3"
    if speed and speed != 1.0:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(raw_path), "-filter:a", f"atempo={speed}", "-vn", str(sped_path)],
            check=True, capture_output=True,
        )
    else:
        sped_path = raw_path

    if not master:
        subprocess.run(["cp", str(sped_path), str(output_path)], check=True)
        return

    chain = (
        "highpass=f=90,"
        "acompressor=threshold=-18dB:ratio=3:attack=5:release=60:makeup=2,"
        "equalizer=f=3200:t=q:w=1.2:g=2.5,"
        "deesser=i=0.15,"
        f"loudnorm=I={loudness_i}:TP={loudness_tp}:LRA={loudness_lra}:print_format=json"
    )
    measure = subprocess.run(
        ["ffmpeg", "-y", "-i", str(sped_path), "-af", chain, "-f", "null", "-"],
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
        ["ffmpeg", "-y", "-i", str(sped_path), "-af", chain2, "-ar", "44100", str(output_path)],
        check=True, capture_output=True,
    )


def main():
    parser = argparse.ArgumentParser(description="Regenerate dialogue via ElevenLabs voice swap + mastering")
    parser.add_argument("--transcript", required=True, help="Path to Scribe transcript JSON")
    parser.add_argument("--male-voice-id", required=True)
    parser.add_argument("--female-voice-id", required=True)
    parser.add_argument("--male-speaker", default="speaker_0")
    parser.add_argument("--female-speaker", default="speaker_1")
    parser.add_argument("--out-dir", required=True, help="Working dir for batch mp3s")
    parser.add_argument("--output", required=True, help="Final mastered mp3 path")
    parser.add_argument("--model-id", default="eleven_v3")
    parser.add_argument("--stability", type=float, default=0.3)
    parser.add_argument("--speed", type=float, default=1.1)
    parser.add_argument("--no-master", action="store_true", help="Skip the mastering chain")
    parser.add_argument("--loudness-i", default="-16", help="Target integrated loudness (LUFS)")
    parser.add_argument("--loudness-tp", default="-1.5", help="Target true peak (dBTP)")
    parser.add_argument("--loudness-lra", default="11", help="Target loudness range (LU)")
    parser.add_argument("--timeout", type=int, default=280)
    args = parser.parse_args()

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        print("[error] ELEVENLABS_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    with open(args.transcript) as f:
        data = json.load(f)

    clean_turns = build_turns(data["words"])
    clean_turns = apply_emotion_tags(clean_turns)
    batches = batch_turns(clean_turns)
    print(f"[info] {len(clean_turns)} turns -> {len(batches)} API batches", file=sys.stderr)

    voice_map = {
        args.male_speaker: args.male_voice_id,
        args.female_speaker: args.female_voice_id,
    }

    out_dir = Path(args.out_dir)
    batch_paths = generate_batches(batches, voice_map, out_dir, api_key, args.model_id, args.stability, args.timeout)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stitch_and_master(
        batch_paths, out_dir, output_path, args.speed,
        master=not args.no_master,
        loudness_i=args.loudness_i, loudness_tp=args.loudness_tp, loudness_lra=args.loudness_lra,
    )
    print(f"[done] final narration -> {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
