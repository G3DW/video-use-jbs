#!/usr/bin/env python3
"""
Chapter Detection - Semantic analysis to find topic shifts in podcast transcripts
"""

import json
import sys
from pathlib import Path


def find_context(words, context_words, window=15):
    """Find timestamp when a specific sequence of words appears"""
    for i in range(len(words) - window):
        text_window = ' '.join([
            words[i+j].get('text', '').strip().lower()
            for j in range(window)
        ])
        if all(cw.lower() in text_window for cw in context_words):
            return words[i]['start'], i
    return None, None


def detect_chapters_ai_topic(transcript_data, min_chapters=3, max_chapters=7):
    """
    Detect chapters for AI/tech podcast topics
    Uses keyword-based detection for common topic transitions
    """
    words = transcript_data.get('words', [])
    if not words:
        return [(0, "Intro")]

    chapters = [(0, "Intro")]

    # Common AI/tech podcast transition markers
    # Each tuple: (search keywords, chapter title)
    ai_markers = [
        (["distillation", "extraction", "process"], "How It Works"),
        (["pricing", "economic", "cost"], "Economic Impact"),
        (["solo", "developer", "small", "business"], "Practical Application"),
        (["operator", "framework", "system"], "Implementation Strategy"),
        (["portable", "modularity", "platform"], "Future-Proofing"),
        (["recap", "pull", "together", "threads"], "Recap"),
    ]

    for context, title in ai_markers:
        ts, idx = find_context(words, context)
        if ts and ts > 60:  # At least 1 minute in
            chapters.append((ts, title))

    # Sort by timestamp
    chapters.sort()

    # Enforce min/max constraints
    if len(chapters) < min_chapters:
        # Add time-based chapters if not enough topic-based ones
        total_duration = words[-1]['end']
        interval = total_duration / (min_chapters + 1)
        for i in range(1, min_chapters - len(chapters) + 1):
            chapters.append((interval * (len(chapters) + i), f"Section {len(chapters) + i}"))
        chapters.sort()

    if len(chapters) > max_chapters:
        # Keep first, last, and evenly distributed middle chapters
        keep_count = max_chapters - 2  # -2 for intro and recap
        step = len(chapters[1:-1]) // keep_count
        kept = [chapters[0]]
        for i in range(1, len(chapters) - 1, step):
            if len(kept) < max_chapters - 1:
                kept.append(chapters[i])
        kept.append(chapters[-1])
        chapters = kept

    return chapters


def detect_chapters_generic(transcript_data, min_chapters=3, max_chapters=7):
    """
    Generic chapter detection using silence gaps and pacing
    Falls back to time-based if no clear topic markers
    """
    words = transcript_data.get('words', [])
    if not words:
        return [(0, "Intro")]

    chapters = [(0, "Intro")]
    total_duration = words[-1]['end']

    # Find natural breaks (silence gaps > 2 seconds)
    silence_breaks = []
    for i in range(len(words) - 1):
        gap = words[i+1]['start'] - words[i]['end']
        if gap > 2.0:  # 2 second silence
            silence_breaks.append((words[i+1]['start'], gap))

    # Sort by gap size and take top candidates
    silence_breaks.sort(key=lambda x: x[1], reverse=True)

    # Use silence breaks as chapter markers
    for ts, gap in silence_breaks[:max_chapters-1]:
        if ts > 60:  # At least 1 minute from start
            chapters.append((ts, f"Chapter {len(chapters) + 1}"))

    # If still not enough chapters, add time-based
    if len(chapters) < min_chapters:
        interval = total_duration / (min_chapters + 1)
        for i in range(len(chapters), min_chapters):
            chapters.append((interval * (i + 1), f"Chapter {i + 1}"))

    chapters.sort()
    return chapters[:max_chapters]


def main():
    if len(sys.argv) < 2:
        print("Usage: detect_chapters.py <transcript.json> [--generic]")
        sys.exit(1)

    transcript_path = Path(sys.argv[1])
    use_generic = "--generic" in sys.argv

    with open(transcript_path) as f:
        data = json.load(f)

    if use_generic:
        chapters = detect_chapters_generic(data)
    else:
        chapters = detect_chapters_ai_topic(data)

    # Output in YouTube format
    for ts, title in chapters:
        mins = int(ts // 60)
        secs = int(ts % 60)
        print(f"{mins:02d}:{secs:02d} - {title}")


if __name__ == "__main__":
    main()
