#!/usr/bin/env python3
"""
Fix Transcript Artifacts — corrects known ElevenLabs Scribe ASR mishearings
of technical terms before the transcript is used to drive TTS resynthesis.

Why this exists: Stage 0 transcribes the raw NotebookLM two-speaker audio,
and that transcript text is what regenerate_dialogue.py hands to ElevenLabs
to *speak*. A handful of technical terms and idioms are homophone-adjacent
enough that Scribe reliably mishears them (SQL -> "Squill", CAPTCHA ->
"KPTCA"/"KPTCAs", "24/7" -> "two and four-seven"). Run BEFORE
regenerate_dialogue.py, this fixes what actually gets spoken, since the ASR
output *is* the TTS script there.

The same mishearing class can also reappear in build_video.py's SECOND
transcription pass — it re-transcribes the final rendered (redubbed) audio
to generate captions, and that's an independent ASR run that can mishear a
word the first pass got right (e.g. correctly-spoken "Claude" heard back as
"Claw"). Run this script again against that second-pass transcript
(edit/transcripts/combined_audio.json) when that happens — at that point
it's a caption-only correction (nothing feeds back into audio), so it's
safe to run post-hoc, repeatedly, on any transcript in this schema.

Deliberately narrow and deterministic: fixed dictionaries of known
mishearings, exact matches only, same replacement every time. Unlike
humanize_transcript.py this never rotates or picks variants — these are
factual corrections, not stylistic variety, so they must be idempotent and
predictable. Extend WORD_ARTIFACTS / PHRASE_ARTIFACTS as new mishearings
turn up in review; don't make this fuzzy-match or LLM-guess, since a wrong
guess here becomes a wrong word spoken in the final audio.

Input:  a Scribe transcript JSON (the schema helpers/transcribe.py
        produces and voice_dialogue.py consumes: a dict with a "words"
        list of {"text","start","end","type","speaker_id",...}). Normally
        the already-humanized transcript, run right after
        humanize_transcript.py and before regenerate_dialogue.py.
Output: a transcript JSON in the identical schema, safe to hand straight
        to regenerate_dialogue.py's --transcript override. Also writes a
        sidecar report listing every correction made, for review.html to
        surface alongside the humanizer swaps.

Usage:
  python3 fix_transcript_artifacts.py --transcript humanized.json \\
      --output humanized.artifact-fixed.json --report artifact-fix-report.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Single-token mishearings: word_regex matched against one word token
# (case-insensitive, whole token only, trailing punctuation ignored).
WORD_ARTIFACTS = [
    {"word_regex": r"^squill$", "replacement": "SQL",
     "note": "ASR mishears 'SQL' (spoken 'sequel') as 'Squill'"},
    {"word_regex": r"^kptcas?$", "replacement": "CAPTCHA", "plural_replacement": "CAPTCHAs",
     "note": "ASR occasionally garbles 'CAPTCHA'/'CAPTCHAs' as 'KPTCA'/'KPTCAs'"},
    {"word_regex": r"^claw$", "replacement": "Claude",
     "note": "ASR mishears standalone 'Claude' as 'Claw' (bleed-through from 'OpenClaw' being said constantly in the same episode) — 'OpenClaw' itself always tokenizes as one word, so this only fires on a bare 'Claw'"},
    {"word_regex": r"^scaleo$", "replacement": "Scalio",
     "note": "ASR hears the product name 'Scalio' (an AI video ad maker) as 'Scaleo' — seen on the dubbed 2026-10-01 episode"},
]

# Learned word fixes (approved by Joe via CommandCenter's apply-learning.js). Loaded from
# a data file instead of editing this source. Entries are validated: single lowercase
# word, 4+ letters, anchored regex, and a single-token replacement. Anything else is ignored.
def _load_learned_artifacts():
    import os
    default = "/Users/joey_makes_stuff/Documents/AgenticOS/CommandCenter/data/morning-pulse/learnings/learned-artifacts.json"
    path = os.environ.get("MORNING_PULSE_LEARNED_ARTIFACTS", default)
    try:
        entries = json.loads(Path(path).read_text()).get("entries", [])
    except Exception:
        return []
    ok = []
    for e in entries:
        rx, rep = e.get("word_regex", ""), e.get("replacement", "")
        if re.fullmatch(r"\^[a-z][a-z']{3,}\$", rx) and isinstance(rep, str) and rep and " " not in rep and len(rep) <= 40:
            ok.append({"word_regex": rx, "replacement": rep, "note": e.get("note", "learned")})
    return ok


WORD_ARTIFACTS.extend(_load_learned_artifacts())

# Multi-word mishearings: regex matched against the reconstructed full
# transcript text (spans multiple word/spacing tokens), spliced out and
# replaced with a single new word token at the matched span's timing.
PHRASE_ARTIFACTS = [
    {"pattern": r"\btwo\s+and\s+four-seven\b", "replacement": "24/7",
     "note": "ASR mishears '24/7' as 'two and four-seven'"},
]


def load_json(path):
    return json.loads(Path(path).read_text())


def fix_words(words, report):
    """Single-token pass: mutate matching word entries in place."""
    for w in words:
        if w.get("type") != "word":
            continue
        text = w["text"]
        stripped = text.strip()
        if not stripped:
            continue
        core = stripped.rstrip(",.!?;:")
        trail_punct = stripped[len(core):]
        for entry in WORD_ARTIFACTS:
            if re.match(entry["word_regex"], core, flags=re.IGNORECASE):
                is_plural = core.lower().endswith("s") and "plural_replacement" in entry
                replacement = entry["plural_replacement"] if is_plural else entry["replacement"]
                if replacement == core:
                    break
                lead = text[: len(text) - len(text.lstrip())]
                new_core = replacement + trail_punct
                w["text"] = f"{lead}{new_core}"
                report.append({
                    "before": stripped, "after": new_core,
                    "start": w.get("start"), "end": w.get("end"),
                    "speaker_id": w.get("speaker_id"), "note": entry["note"],
                })
                break
    return words


def reconstruct(words):
    parts, index_map = [], []
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


def fix_phrases(words, report):
    """Multi-token pass: regex over the reconstructed text, splice matched
    word ranges back-to-front so earlier indices stay valid."""
    full_text, index_map = reconstruct(words)
    matches = []
    for entry in PHRASE_ARTIFACTS:
        for m in re.finditer(entry["pattern"], full_text, flags=re.IGNORECASE):
            matches.append((m.start(), m.end(), entry))
    matches.sort(key=lambda x: -x[0])  # back-to-front

    for start_c, end_c, entry in matches:
        rng = word_range_for_span(index_map, start_c, end_c)
        if not rng:
            continue
        lo, hi = rng
        speaker_id = words[lo]["speaker_id"]
        start_t, end_t = words[lo]["start"], words[hi - 1]["end"]
        original = "".join(w["text"] for w in words[lo:hi]).strip()

        new_word = {
            "text": entry["replacement"], "start": start_t, "end": end_t,
            "type": "word", "speaker_id": speaker_id, "logprob": 0.0,
        }
        words[lo:hi] = [new_word]
        report.append({
            "before": original, "after": entry["replacement"],
            "start": start_t, "end": end_t,
            "speaker_id": speaker_id, "note": entry["note"],
        })
    return words


def main():
    ap = argparse.ArgumentParser(description="Correct known ASR mishearings of technical terms/idioms before TTS resynthesis")
    ap.add_argument("--transcript", required=True, help="Path to a Scribe transcript JSON (normally already humanized)")
    ap.add_argument("--output", required=True, help="Path to write the corrected transcript JSON")
    ap.add_argument("--report", required=True, help="Path to write the correction report JSON")
    args = ap.parse_args()

    data = load_json(args.transcript)
    report = []
    data["words"] = fix_words(data["words"], report)
    data["words"] = fix_phrases(data["words"], report)
    if "text" in data:
        data["text"] = "".join(w["text"] for w in data["words"])

    Path(args.output).write_text(json.dumps(data, indent=2))
    Path(args.report).write_text(json.dumps(report, indent=2))

    if report:
        print(f"[done] {len(report)} artifact(s) corrected -> {args.output}", file=sys.stderr)
        for r in report:
            print(f"  [{r['speaker_id']}] \"{r['before']}\" -> \"{r['after']}\" ({r['note']})", file=sys.stderr)
    else:
        print(f"[done] no known ASR artifacts found -> {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
