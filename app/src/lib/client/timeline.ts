import type { Edl, EdlRange, WordEntry } from "../types";

export interface OutputSegment extends EdlRange {
  index: number;
  offset: number; // start in output timeline
  dur: number;
}

export function outputSegments(edl: Edl | null): OutputSegment[] {
  if (!edl) return [];
  let offset = 0;
  return edl.ranges.map((r, index) => {
    const dur = Math.max(0, r.end - r.start);
    const seg = { ...r, index, offset, dur };
    offset += dur;
    return seg;
  });
}

export function totalDuration(edl: Edl | null): number {
  return outputSegments(edl).reduce((a, s) => a + s.dur, 0);
}

/** Map an output-timeline time to {segment, sourceTime}. */
export function outputToSource(edl: Edl | null, t: number): { seg: OutputSegment; sourceT: number } | null {
  for (const seg of outputSegments(edl)) {
    if (t >= seg.offset && t < seg.offset + seg.dur) {
      return { seg, sourceT: seg.start + (t - seg.offset) };
    }
  }
  return null;
}

/** Map a source phrase range to its EDL coverage status. */
export function phraseCoverage(
  edl: Edl | null,
  source: string,
  start: number,
  end: number
): "kept" | "cut" | "partial" {
  if (!edl) return "cut";
  let covered = 0;
  for (const r of edl.ranges) {
    if (r.source !== source) continue;
    const s = Math.max(start, r.start);
    const e = Math.min(end, r.end);
    if (e > s) covered += e - s;
  }
  const total = end - start;
  if (covered >= total * 0.85) return "kept";
  if (covered <= total * 0.1) return "cut";
  return "partial";
}

/**
 * Snap a raw time to a word boundary with SKILL padding (Hard Rules 6+7):
 * cut-in lands pad_before ahead of a word start; cut-out lands pad_after
 * past a word end. Falls back to the raw time when no words are known.
 */
export function snapToWord(
  words: WordEntry[],
  t: number,
  edge: "start" | "end",
  padBefore = 0.05,
  padAfter = 0.08
): number {
  if (!words.length) return t;
  let best = t;
  let bestDist = Infinity;
  for (const w of words) {
    const cand = edge === "start" ? Math.max(0, w.s - padBefore) : w.e + padAfter;
    const d = Math.abs(cand - t);
    if (d < bestDist) {
      bestDist = d;
      best = cand;
    }
  }
  return Math.round(best * 1000) / 1000;
}

export function fmtTime(t: number): string {
  if (!isFinite(t)) return "0:00.0";
  const m = Math.floor(t / 60);
  const s = t - m * 60;
  return `${m}:${s.toFixed(1).padStart(4, "0")}`;
}

export function fmtClock(t: number): string {
  const m = Math.floor(t / 60);
  const s = Math.floor(t - m * 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

const BEAT_COLORS = ["#2dd4bf", "#818cf8", "#fbbf24", "#f472b6", "#60a5fa", "#34d399", "#fb923c"];
export function beatColor(beat: string | undefined): string {
  if (!beat) return "#7c8aa0";
  let h = 0;
  for (const c of beat) h = (h * 31 + c.charCodeAt(0)) % 997;
  return BEAT_COLORS[h % BEAT_COLORS.length];
}
