#!/usr/bin/env python3
"""Sentence-by-sentence speaker view of a transcript, for review.html.

Groups consecutive words by speaker_id into turns, prints each turn as
"YOUR VOICE / HOPE: text", and flags every spot where the speaker changes in the
middle of a sentence (previous turn does not end in . ? ! or similar) -- the
signature of bad diarization (one word dubbed in the wrong voice).

Usage:
    speaker_turns.py <transcript.json> [--speaker-map edit/speaker_map.json]
                     [--format html|md|json]

The html output is a fragment (no <html>/<body>) to paste into review.html.
Exit code is 0 always; the flag count is printed on the first line of md/html
output and in the json "midSentenceSwitches" field.
"""
import argparse, html, json, re, sys
from pathlib import Path

END = re.compile(r'[.?!…]["\'”’)\]]*$')


def load_turns(path):
    d = json.loads(Path(path).read_text())
    words = [w for w in d["words"] if w.get("type", "word") == "word"]
    turns = []
    for w in words:
        sp = w.get("speaker_id")
        if turns and turns[-1]["speaker"] == sp:
            turns[-1]["words"].append(w)
        else:
            turns.append({"speaker": sp, "words": [w]})
    for i, t in enumerate(turns):
        t["start"] = t["words"][0]["start"]
        t["text"] = " ".join(w["text"].strip() for w in t["words"]).replace(" ,", ",")
        # flagged if the PREVIOUS turn stopped mid-sentence
        t["midSentence"] = i > 0 and not END.search(turns[i - 1]["text"])
    return turns


def label_for(speaker, smap):
    if smap:
        if speaker == smap.get("male_speaker"):
            return f"YOUR VOICE ({speaker})"
        if speaker == smap.get("female_speaker"):
            return f"HOPE ({speaker})"
    return speaker or "?"


def fmt(sec):
    return f"{int(sec // 60)}:{int(sec % 60):02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("--speaker-map")
    ap.add_argument("--format", choices=["html", "md", "json"], default="md")
    a = ap.parse_args()
    smap = json.loads(Path(a.speaker_map).read_text()) if a.speaker_map else None
    turns = load_turns(a.transcript)
    flags = sum(t["midSentence"] for t in turns)
    if a.format == "json":
        json.dump({"turns": [{"speaker": t["speaker"], "start": t["start"], "text": t["text"],
                              "midSentence": t["midSentence"]} for t in turns],
                   "midSentenceSwitches": flags}, sys.stdout, indent=1)
        return
    if a.format == "md":
        print(f"{len(turns)} turns, {flags} speaker switches mid-sentence")
        for t in turns:
            mark = "  <-- switch mid-sentence" if t["midSentence"] else ""
            print(f"[{fmt(t['start'])}] {label_for(t['speaker'], smap)}: {t['text']}{mark}")
        return
    status = ("ok: no speaker switches mid-sentence" if flags == 0 else
              f"WARNING: {flags} speaker switches land mid-sentence (highlighted); "
              "a word may be dubbed in the wrong voice")
    warn_style = " style='color:#b00;font-weight:bold'" if flags else ""
    print(f'<p class="turn-status"{warn_style}>'
          f'{len(turns)} turns. {html.escape(status)}</p>')
    print('<div class="turns">')
    for t in turns:
        sty = ' style="background:#fff3cd;border-left:4px solid #e0a800;padding:2px 6px"' if t["midSentence"] else ""
        print(f'<p{sty}><small>{fmt(t["start"])}</small> <b>{html.escape(label_for(t["speaker"], smap))}:</b> '
              f'{html.escape(t["text"])}</p>')
    print('</div>')


if __name__ == "__main__":
    main()
