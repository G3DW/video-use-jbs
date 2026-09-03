#!/usr/bin/env python3
"""
Normalize Caption Numbers — rewrites spoken-word dates, version numbers,
and a couple of common spoken-idiom numbers into conventional digit form
for captions/transcript/karaoke text, WITHOUT touching what was actually
spoken. This is a display-only pass.

Why this is separate from fix_transcript_artifacts.py: that script fixes
actual ASR mishearings that get fed into TTS and so change what's spoken
in the audio. This script runs the other direction — on the transcript of
the FINAL rendered audio (after redub, after build_video.py's own
re-transcription), correcting how normal, correctly-heard speech gets
displayed. "August thirty-first, twenty twenty-six" was transcribed
correctly (that's genuinely what's spoken); it just reads better as
"August 31, 2026" on screen. Never run this before TTS — feeding digit
text back into ElevenLabs is a separate, riskier change (some models
mispronounce a raw "2.0" or "8/31/2026"); leave spoken audio as words.

Handles, in the reconstructed full transcript text:
  - Version numbers:  "two point o"            -> "2.0"
  - Dates:            "August thirty-first, twenty twenty-six" -> "August 31, 2026"
  - 24/7 idiom:        "twenty-four seven" / "twenty four seven" -> "24/7"

Deliberately conservative: only fires on patterns it can fully parse via
the number-word dictionaries below. An unparseable date/number is left as
spoken words rather than guessed at — a wrong digit in a caption is worse
than a spelled-out one.

Input:  a Scribe transcript JSON (words list), e.g. build_video.py's
        edit/transcripts/combined_audio.json, AFTER transcription.
Output: a transcript JSON in the identical schema. Re-run build_video.py
        with --skip-transcribe (or generate_broll.py's caption build step)
        against this corrected file to regenerate subtitles/transcript/
        karaoke captions from the normalized text.

Usage:
  python3 normalize_caption_numbers.py --transcript combined_audio.json \\
      --output combined_audio.captions-normalized.json --report caption-normalize-report.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

ONES = {
    "zero": 0, "oh": 0, "o": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
}
TEENS = {
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
ORDINAL = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11,
    "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15,
    "sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19,
    "twentieth": 20, "thirtieth": 30, "thirty-first": 31,
}
CARDINAL = {**ONES, **TEENS, **TENS}
MONTHS = [
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
]


def word_to_number(word):
    """Parse a cardinal or ordinal number word (possibly hyphenated, e.g.
    'twenty-six' or 'thirty-first') into an int, or None if unparseable."""
    w = word.lower().strip(",.!?;:")
    if w in ORDINAL:
        return ORDINAL[w]
    if w in CARDINAL:
        return CARDINAL[w]
    if "-" in w:
        parts = w.split("-")
        if len(parts) == 2:
            tens_w, ones_w = parts
            tens = CARDINAL.get(tens_w)
            ones = CARDINAL.get(ones_w) if ones_w not in ORDINAL else ORDINAL[ones_w]
            if tens is not None and ones is not None and tens in TENS.values():
                return tens + ones
    return None


def reconstruct(words):
    parts, index_map = [], []
    for i, w in enumerate(words):
        parts.append(w["text"])
        index_map.extend([i] * len(w["text"]))
    return "".join(parts), index_map


def word_range_for_span(index_map, start_char, end_char):
    if not index_map or start_char >= len(index_map) or end_char - 1 >= len(index_map):
        return None
    lo = index_map[start_char]
    hi = index_map[end_char - 1] + 1
    return lo, hi


VERSION_RE = re.compile(r"\b([a-z]+)\s+point\s+([a-z]+)\b", re.IGNORECASE)
DATE_RE = re.compile(
    r"\b(" + "|".join(MONTHS) + r")\s+([a-z-]+),?\s+twenty\s+([a-z-]+),?",
    re.IGNORECASE,
)
TWENTY_FOUR_SEVEN_RE = re.compile(r"\btwenty[\s-]?four[\s/-]+seven\b", re.IGNORECASE)


def find_matches(full_text):
    matches = []

    for m in VERSION_RE.finditer(full_text):
        major = word_to_number(m.group(1))
        minor = word_to_number(m.group(2))
        if major is None or minor is None:
            continue
        matches.append((m.start(), m.end(), f"{major}.{minor}",
                         f"version number '{m.group(0).strip()}'"))

    for m in DATE_RE.finditer(full_text):
        month, day_w, year_w = m.group(1), m.group(2), m.group(3)
        day = word_to_number(day_w)
        year_tail = word_to_number(year_w)
        if day is None or year_tail is None or not (1 <= day <= 31):
            continue
        year = 2000 + year_tail
        matches.append((m.start(), m.end(), f"{month.capitalize()} {day}, {year}",
                         f"date '{m.group(0).strip()}'"))

    for m in TWENTY_FOUR_SEVEN_RE.finditer(full_text):
        matches.append((m.start(), m.end(), "24/7", f"idiom '{m.group(0).strip()}'"))

    matches.sort(key=lambda x: x[0])
    accepted, last_end = [], -1
    for start_c, end_c, replacement, note in matches:
        if start_c < last_end:
            continue
        accepted.append((start_c, end_c, replacement, note))
        last_end = end_c
    return accepted


def normalize(words, report):
    full_text, index_map = reconstruct(words)
    accepted = find_matches(full_text)

    for start_c, end_c, replacement, note in sorted(accepted, key=lambda x: -x[0]):
        rng = word_range_for_span(index_map, start_c, end_c)
        if not rng:
            continue
        lo, hi = rng
        speaker_id = words[lo]["speaker_id"]
        start_t, end_t = words[lo]["start"], words[hi - 1]["end"]
        original = "".join(w["text"] for w in words[lo:hi]).strip()
        # the matched word-token range can extend past the regex match
        # itself (e.g. "o's" — the "'s" trails the "point o" match inside
        # the same token) since splicing works at whole-token granularity;
        # carry that trailing text over instead of dropping it.
        matched_text = full_text[start_c:end_c]
        suffix = original[len(matched_text):] if original.startswith(matched_text) else ""
        new_word = {
            "text": replacement + suffix, "start": start_t, "end": end_t,
            "type": "word", "speaker_id": speaker_id, "logprob": 0.0,
        }
        words[lo:hi] = [new_word]
        report.append({"before": original, "after": replacement + suffix, "note": note,
                        "start": start_t, "end": end_t, "speaker_id": speaker_id})
    return words


def main():
    ap = argparse.ArgumentParser(description="Normalize spoken dates/version numbers/idioms to digit form for captions only")
    ap.add_argument("--transcript", required=True, help="Path to the final-audio Scribe transcript JSON")
    ap.add_argument("--output", required=True, help="Path to write the caption-normalized transcript JSON")
    ap.add_argument("--report", required=True, help="Path to write the normalization report JSON")
    args = ap.parse_args()

    data = json.loads(Path(args.transcript).read_text())
    report = []
    data["words"] = normalize(data["words"], report)
    if "text" in data:
        data["text"] = "".join(w["text"] for w in data["words"])

    Path(args.output).write_text(json.dumps(data, indent=2))
    Path(args.report).write_text(json.dumps(report, indent=2))

    if report:
        print(f"[done] {len(report)} caption normalization(s) -> {args.output}", file=sys.stderr)
        for r in report:
            print(f"  \"{r['before']}\" -> \"{r['after']}\" ({r['note']})", file=sys.stderr)
    else:
        print(f"[done] no normalizable dates/numbers found -> {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
