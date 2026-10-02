#!/usr/bin/env python3
"""Print an episode's sentences with timestamps and speakers, to pick vertical-clip boundaries.

    list_sentences.py --episode-dir <Content/DATE-podcast> [--from 120] [--to 200]

Uses edit/transcripts/combined_audio.json (the timings of the final video's audio). A good clip
(see shorts_config.json: 45-75s) starts on a sentence that works as a hook and ends on a sentence
end; copy the start of the first word and the end of the last word into clips.json.
Speaker H = speaker_0 (Hope), J = speaker_1 (Joe); this is the episode's usual mapping, check
edit/speaker_map.json if in doubt.
"""
import argparse
import json
from pathlib import Path


def sentences(words):
    cur, out = [], []
    for w in words:
        if w.get("type") != "word":
            continue
        cur.append(w)
        if w["text"].strip().endswith((".", "?", "!")) and len(cur) >= 2:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode-dir", required=True)
    ap.add_argument("--from", dest="t_from", type=float, default=0)
    ap.add_argument("--to", dest="t_to", type=float, default=1e9)
    ap.add_argument("--width", type=int, default=110)
    args = ap.parse_args()
    path = Path(args.episode_dir) / "edit" / "transcripts" / "combined_audio.json"
    words = json.loads(path.read_text())["words"]
    for s in sentences(words):
        a, b = s[0]["start"], s[-1]["end"]
        if b < args.t_from or a > args.t_to:
            continue
        sp = {"speaker_0": "H", "speaker_1": "J"}.get(s[0].get("speaker_id"), "?")
        text = " ".join(w["text"] for w in s)
        print(f"{a:7.2f} - {b:7.2f}  {sp}  {text[:args.width]}")


if __name__ == "__main__":
    main()
