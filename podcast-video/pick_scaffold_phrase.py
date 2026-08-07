#!/usr/bin/env python3
"""
Pick Scaffold Phrase — small companion to humanize_transcript.py for the
two scaffold categories that DON'T live in NotebookLM's raw dialogue and
therefore can't be caught by regex-scanning the transcript: the
"Let's get into it." cold-open close and the "drop a like ... subscribe
... see you next time" CTA. Those two are freehand-drafted by Claude into
intro.txt/outro.txt at Stage 2 Step 3 (build_video.py synthesizes them
separately, in Joe's own cloned voice, and prepends/appends them around
the dubbed dialogue) — and in practice they've been drafted with the same
skeleton nearly every episode. This script pulls the next non-repeated
variant from the same humanizer_phrases.json / humanizer_state.json used
by humanize_transcript.py, so intro/outro drafting stays in the same
rotation and doesn't fall back to habit.

Usage:
  # Opening close (goes at the end of intro.txt, replaces "Let's get into it."):
  python3 pick_scaffold_phrase.py --category opening_energizer

  # Closing CTA (goes at the end of outro.txt; --ask is the per-episode
  # comment prompt, e.g. "comment which model you'd trust with production data"):
  python3 pick_scaffold_phrase.py --category cta_outro \\
      --ask "comment which connector you're checking first"

Prints the chosen phrase to stdout and persists the rotation state.
"""

import argparse
import json
import random
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PHRASE_BANK_PATH = SCRIPT_DIR / "humanizer_phrases.json"
STATE_PATH = SCRIPT_DIR / "humanizer_state.json"
NO_REPEAT_WINDOW = 4


def load_json(path, default=None):
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text())
    return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", required=True, help="e.g. opening_energizer, cta_outro")
    ap.add_argument("--ask", default=None, help="Required for template categories like cta_outro — the per-episode comment prompt")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--no-save-state", action="store_true")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    bank = json.loads(PHRASE_BANK_PATH.read_text())
    if args.category not in bank:
        sys.exit(f"[error] unknown category '{args.category}' — options: {', '.join(k for k in bank if not k.startswith('_'))}")
    entry = bank[args.category]

    state = load_json(STATE_PATH, default={})
    recent = state.get(args.category, [])
    pool = entry["alternatives"]
    candidates = [v for v in pool if v not in recent[-NO_REPEAT_WINDOW:]]
    if not candidates:
        candidates = pool
    template_pick = random.choice(candidates)  # un-formatted — this is what we track for no-repeat purposes

    if entry.get("template"):
        if not args.ask:
            sys.exit(f"[error] category '{args.category}' is a template — pass --ask \"...\"")
        output = template_pick.format(ask=args.ask.strip(" ,."))
    else:
        output = template_pick

    recent.append(template_pick)
    state[args.category] = recent[-20:]

    if not args.no_save_state:
        STATE_PATH.write_text(json.dumps(state, indent=2))

    print(output)


if __name__ == "__main__":
    main()
