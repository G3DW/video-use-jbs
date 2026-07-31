"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useStudio } from "./studio";
import { frameUrl } from "@/lib/client/api";
import { beatColor, fmtClock, outputSegments, snapToWord, totalDuration } from "@/lib/client/timeline";
import type { Edl } from "@/lib/types";

/**
 * Output-timeline with three tracks: video segments (draggable word-snapped
 * edges), animation overlays, subtitle presence. Click to seek. Wheel zoom.
 */
export default function Timeline() {
  const st = useStudio();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [pxPerSec, setPxPerSec] = useState(0); // 0 = fit
  const edl = st.draftEdl ?? st.proj?.edl ?? null;
  const segs = useMemo(() => outputSegments(edl), [edl]);
  const total = useMemo(() => totalDuration(edl), [edl]);

  const [fitPx, setFitPx] = useState(6);
  useEffect(() => {
    const el = scrollRef.current;
    if (el && total > 0) setFitPx(Math.max(1.5, (el.clientWidth - 20) / total));
  }, [total]);
  const pps = pxPerSec || fitPx;

  const drag = useRef<{
    index: number;
    edge: "start" | "end";
    startX: number;
    orig: number;
  } | null>(null);

  // prefetch words for sources being dragged
  const beginDrag = useCallback(
    (index: number, edge: "start" | "end", e: React.PointerEvent) => {
      e.stopPropagation();
      e.preventDefault();
      if (!edl) return;
      drag.current = { index, edge, startX: e.clientX, orig: edl.ranges[index][edge] };
      st.getWords(edl.ranges[index].source).catch(() => {});
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    },
    [edl, st]
  );

  const onDragMove = useCallback(
    (e: React.PointerEvent) => {
      const d = drag.current;
      if (!d || !edl) return;
      const deltaSec = (e.clientX - d.startX) / pps;
      const next = structuredClone(st.proj?.edl ?? edl) as Edl;
      const r = next.ranges[d.index];
      if (d.edge === "start") {
        r.start = Math.max(0, Math.min(d.orig + deltaSec, r.end - 0.15));
      } else {
        r.end = Math.max(r.start + 0.15, d.orig + deltaSec);
      }
      st.setDraftEdl(next);
    },
    [edl, pps, st]
  );

  const endDrag = useCallback(async () => {
    const d = drag.current;
    drag.current = null;
    if (!d || !st.draftEdl) return;
    // snap the moved edge to a word boundary (Hard Rules 6+7)
    const next = structuredClone(st.draftEdl) as Edl;
    const r = next.ranges[d.index];
    try {
      const words = await st.getWords(r.source);
      if (d.edge === "start") r.start = Math.min(snapToWord(words, r.start, "start"), r.end - 0.1);
      else r.end = Math.max(snapToWord(words, r.end, "end"), r.start + 0.1);
    } catch {}
    st.setDraftEdl(next);
    // commit
    setTimeout(() => st.commitDraft(), 0);
  }, [st]);

  const seekAt = useCallback(
    (e: React.MouseEvent) => {
      const el = scrollRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const x = e.clientX - rect.left + el.scrollLeft;
      st.seek(Math.max(0, Math.min(total, x / pps)));
    },
    [pps, st, total]
  );

  if (!edl || segs.length === 0) {
    return (
      <div className="panel timeline-panel">
        <div className="panel-h">
          <span className="sec-label" style={{ flex: 1 }}>Timeline</span>
        </div>
        <div className="no-media">
          no EDL yet — ask the agent to propose a cut, and the timeline appears here
        </div>
      </div>
    );
  }

  const width = Math.max(total * pps + 20, 300);
  const tickEvery = pps > 40 ? 5 : pps > 12 ? 15 : pps > 4 ? 30 : 60;
  const ticks: number[] = [];
  for (let t = 0; t <= total; t += tickEvery) ticks.push(t);

  const overlays = edl.overlays ?? [];
  const subActive = !!edl.subtitles;

  return (
    <div className="panel timeline-panel">
      <div className="panel-h">
        <span className="sec-label" style={{ flex: 1 }}>
          Timeline · {segs.length} segments · {fmtClock(total)}
        </span>
        <button className="btn small ghost" onClick={() => setPxPerSec(0)} title="Fit">
          fit
        </button>
        <button className="btn small ghost" onClick={() => setPxPerSec(Math.min(pps * 1.5, 200))}>
          +
        </button>
        <button className="btn small ghost" onClick={() => setPxPerSec(Math.max(pps / 1.5, fitPx))}>
          −
        </button>
      </div>
      <div className="tl-scroll" ref={scrollRef} onPointerMove={onDragMove} onPointerUp={endDrag}>
        <div className="tl-inner" style={{ width }} onClick={seekAt}>
          <div className="tl-ruler">
            {ticks.map((t) => (
              <div key={t} className="tl-tick" style={{ left: t * pps }}>
                {fmtClock(t)}
              </div>
            ))}
          </div>

          <div className="tl-track">
            {segs.map((s) => {
              const rel = st.proj?.resolvedSources[s.source];
              const thumb = rel
                ? `url(${frameUrl(st.dir, rel, (s.start + s.end) / 2, 160)})`
                : undefined;
              const selected = st.selection === s.index;
              return (
                <div
                  key={s.index}
                  className={`tl-seg${selected ? " selected" : ""}`}
                  style={{
                    left: s.offset * pps,
                    width: Math.max(3, s.dur * pps - 2),
                    backgroundImage: thumb,
                    borderTopColor: beatColor(s.beat),
                    borderTopWidth: 3,
                  }}
                  title={`${s.source} ${s.start.toFixed(2)}–${s.end.toFixed(2)}\n${s.beat ?? ""}\n${s.reason ?? ""}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    st.setSelection(s.index);
                    st.seek(s.offset + 0.01);
                  }}
                >
                  {s.dur * pps > 46 && <span className="beat">{s.beat}</span>}
                  {s.dur * pps > 60 && <span className="src">{s.source}</span>}
                  {selected && (
                    <>
                      <div className="tl-handle l" onPointerDown={(e) => beginDrag(s.index, "start", e)} />
                      <div className="tl-handle r" onPointerDown={(e) => beginDrag(s.index, "end", e)} />
                    </>
                  )}
                </div>
              );
            })}
          </div>

          <div className="tl-track small">
            <span className="tl-track-label">overlays</span>
            {overlays.map((o, i) => (
              <div
                key={i}
                className="tl-ovl"
                style={{ left: o.start_in_output * pps, width: Math.max(20, o.duration * pps) }}
                title={o.file}
              >
                {o.file.split("/").slice(-2)[0]}
              </div>
            ))}
          </div>

          <div className="tl-track small">
            <span className="tl-track-label">subtitles</span>
            {subActive && <div className="tl-sub" style={{ left: 0, width: total * pps }} />}
          </div>

          <div className="tl-playhead" style={{ left: st.playhead * pps }} />
        </div>
      </div>
    </div>
  );
}
