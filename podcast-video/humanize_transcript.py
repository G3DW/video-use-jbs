#!/usr/bin/env python3
"""
Humanize Transcript — swaps NotebookLM's recurring scaffold phrases (the
"let's unpack this" / "which brings us to" / mull-over closer / CTA outro
kind of connective tissue that repeats nearly verbatim episode to episode)
for a rotating bank of alternatives, so the show doesn't develop an
audible template once you binge more than a couple episodes in a row.

Deliberately narrow scope: only touches fixed transitional/structural
phrasing defined in humanizer_phrases.json. Never touches analogies,
stats, quotes, or anything topic-specific — those already vary naturally
episode to episode and are exactly what gets fact-checked against the raw
transcript before anything is dubbed, so this pass must not be able to
introduce a factual error. If a category isn't in the phrase bank, this
script has no way to touch it — that's the safety boundary, not an
oversight.

Input:  a Scribe transcript JSON (the schema helpers/transcribe.py
        produces and voice_dialogue.py consumes: a dict with a "words"
        list of {"text","start","end","type","speaker_id",...}).
Output: a transcript JSON in the identical schema — safe to hand straight
        to regenerate_dialogue.py's --transcript override (or
        voice_dialogue.py's --transcript) in place of the raw one, and
        safe for anchorQuote text-matching in storyboard-plan.json since
        the swapped text is exactly what gets spoken. Also writes a
        sidecar report listing every swap made (category, before, after)
        for review.html to surface — Joe should see exactly what changed
        in the same pass he already reviews for factual accuracy.

Rotation state persists in humanizer_state.json (next to this script) —
keeps the last N picks per category so the same alternative doesn't run
twice in a row across episodes. State is updated even on a dry run unless
--no-save-state is passed.

Usage:
  python3 humanize_transcript.py --transcript raw.json --output humanized.json \\
      --report humanize-report.json --date 2026-08-05
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PHRASE_BANK_PATH = SCRIPT_DIR / "humanizer_phrases.json"
STATE_PATH = SCRIPT_DIR / "humanizer_state.json"
NO_REPEAT_WINDOW = 4  # a variant won't repeat until this many other picks (per category) have happened


def load_json(path, default=None):
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text())
    return default


def reconstruct(words):
    """Concatenate every word's raw text into one string, plus a parallel
    char-index -> word-list-index map, so a regex match against the plain
    text can be translated back into a [start_idx, end_idx) word slice."""
    parts = []
    index_map = []
    for i, w in enumerate(words):
        t = w["text"]
        parts.append(t)
        index_map.extend([i] * len(t))
    return "".join(parts), index_map


def word_range_for_span(index_map, start_char, end_char):
    if not index_map or start_char >= len(index_map) or end_char - 1 >= len(index_map):
        return None
    lo = index_map[start_char]
    hi = index_map[end_char - 1] + 1
    return lo, hi


def pick_variant(entry, category, used_this_episode, state):
    recent = state.get(category, [])
    pool = entry["alternatives"]
    candidates = [v for v in pool if v not in recent[-NO_REPEAT_WINDOW:] and v not in used_this_episode]
    if not candidates:
        candidates = [v for v in pool if v not in used_this_episode]
    if not candidates:
        candidates = pool
    choice = random.choice(candidates)
    used_this_episode.add(choice)
    recent.append(choice)
    state[category] = recent[-20:]
    return choice


def make_replacement_words(text, speaker_id, start_t, end_t):
    """Turn a plain string into word/spacing entries matching Scribe's
    schema, with timestamps evenly interpolated across the original
    span's [start_t, end_t] window. Precision doesn't matter downstream —
    voice_dialogue.py re-times everything on resynthesis and
    build_video.py re-transcribes the final render — this only keeps the
    schema valid for anything that reads it before that point (review.html,
    storyboard anchorQuote matching)."""
    tokens = re.findall(r"\S+|\s+", text)
    n = max(len(tokens), 1)
    span = max(end_t - start_t, 0.01)
    step = span / n
    out = []
    t = start_t
    for tok in tokens:
        typ = "spacing" if tok.isspace() else "word"
        out.append({
            "text": tok,
            "start": round(t, 3),
            "end": round(t + step, 3),
            "type": typ,
            "speaker_id": speaker_id,
            "logprob": 0.0,
        })
        t += step
    return out


def find_matches(full_text, bank):
    matches = []
    for category, entry in bank.items():
        if category.startswith("_"):
            continue
        for pattern in entry["detect"]:
            for m in re.finditer(pattern, full_text, flags=re.IGNORECASE | re.DOTALL):
                matches.append((m.start(), m.end(), category, entry, m))
    matches.sort(key=lambda x: x[0])

    accepted = []
    last_end = -1
    for start_c, end_c, category, entry, m in matches:
        if start_c < last_end:
            continue  # overlaps an already-accepted (earlier) match — skip
        accepted.append((start_c, end_c, category, entry, m))
        last_end = end_c
    return accepted


def apply_swaps(words, bank, state, used_this_episode, report):
    full_text, index_map = reconstruct(words)
    accepted = find_matches(full_text, bank)

    # Splice back-to-front so earlier word-list indices stay valid while mutating.
    for start_c, end_c, category, entry, m in sorted(accepted, key=lambda x: -x[0]):
        rng = word_range_for_span(index_map, start_c, end_c)
        if not rng:
            continue
        lo, hi = rng
        speaker_id = words[lo]["speaker_id"]
        start_t, end_t = words[lo]["start"], words[hi - 1]["end"]
        original = "".join(w["text"] for w in words[lo:hi]).strip()

        template_text = pick_variant(entry, category, used_this_episode, state)
        if entry.get("template"):
            groupdict = m.groupdict()
            ask = (groupdict.get("ask") or "").strip(" ,.")
            if not ask:
                continue  # capture group came back empty — skip rather than emit a broken sentence
            replacement = template_text.format(ask=ask)
        else:
            replacement = template_text

        new_words = make_replacement_words(replacement, speaker_id, start_t, end_t)
        words[lo:hi] = new_words
        report.append({"category": category, "before": original, "after": replacement})

    return words


def main():
    ap = argparse.ArgumentParser(description="Rotate NotebookLM's repeated scaffold phrases before dubbing")
    ap.add_argument("--transcript", required=True, help="Path to raw Scribe transcript JSON")
    ap.add_argument("--output", required=True, help="Path to write the humanized transcript JSON")
    ap.add_argument("--report", required=True, help="Path to write the swap report JSON")
    ap.add_argument("--date", required=True, help="Episode date (YYYY-MM-DD) — label only, doesn't affect matching")
    ap.add_argument("--seed", type=int, default=None, help="Fixed RNG seed, for reproducible test runs")
    ap.add_argument("--no-save-state", action="store_true", help="Don't persist rotation state (dry runs)")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    if not PHRASE_BANK_PATH.exists():
        sys.exit(f"[error] phrase bank not found: {PHRASE_BANK_PATH}")
    bank = json.loads(PHRASE_BANK_PATH.read_text())
    state = load_json(STATE_PATH, default={})

    data = json.loads(Path(args.transcript).read_text())
    report = []
    used_this_episode = set()
    data["words"] = apply_swaps(data["words"], bank, state, used_this_episode, report)

    Path(args.output).write_text(json.dumps(data, indent=2))
    Path(args.report).write_text(json.dumps({"date": args.date, "swaps": report}, indent=2))
    if not args.no_save_state:
        STATE_PATH.write_text(json.dumps(state, indent=2))

    print(f"[done] {len(report)} phrase(s) swapped -> {args.output}", file=sys.stderr)
    for r in report:
        before_preview = r["before"][:60] + ("..." if len(r["before"]) > 60 else "")
        print(f"  [{r['category']}] \"{before_preview}\" -> \"{r['after']}\"", file=sys.stderr)


if __name__ == "__main__":
    main()
