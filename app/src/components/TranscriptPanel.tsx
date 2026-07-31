"use client";

import { useMemo, useState } from "react";
import { useStudio } from "./studio";
import { outputSegments, phraseCoverage } from "@/lib/client/timeline";

/**
 * takes_packed.md as a reading view: every take, every phrase with its
 * [start-end] range. Kept ranges are highlighted from the EDL; clicking a kept
 * phrase seeks the preview to that moment in the output timeline.
 */
export default function TranscriptPanel() {
  const st = useStudio();
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [filter, setFilter] = useState("");
  const edl = st.proj?.edl ?? null;
  const segs = useMemo(() => outputSegments(edl), [edl]);

  const takes = st.proj?.takes ?? [];

  if (!takes.length) {
    return (
      <div className="panel ed-left">
        <div className="panel-h"><span className="sec-label" style={{ flex: 1 }}>Transcript</span></div>
        <div className="no-media">
          no takes_packed.md yet —<br />
          run Transcribe then Pack from the console
        </div>
      </div>
    );
  }

  const seekPhrase = (source: string, start: number) => {
    const seg = segs.find((s) => s.source === source && start >= s.start - 0.2 && start < s.end);
    if (seg) st.seek(seg.offset + Math.max(0, start - seg.start));
  };

  /** Add a cut-out phrase back into the EDL as its own range, in chronological position. */
  const keepPhrase = (source: string, start: number, end: number, text: string) => {
    st.updateEdl((edl) => {
      const range = {
        source,
        start: Math.max(0, Math.round((start - 0.05) * 1000) / 1000), // pad (Hard Rule 7)
        end: Math.round((end + 0.08) * 1000) / 1000,
        beat: "RESTORED",
        quote: text.slice(0, 60),
        reason: "restored from transcript in the studio",
      };
      // insert after the last range of the same source that ends before this phrase
      let at = edl.ranges.length;
      for (let i = edl.ranges.length - 1; i >= 0; i--) {
        if (edl.ranges[i].source === source && edl.ranges[i].end <= start + 0.2) {
          at = i + 1;
          break;
        }
      }
      edl.ranges.splice(at, 0, range);
      return edl;
    });
  };

  return (
    <div className="panel ed-left">
      <div className="panel-h">
        <span className="sec-label" style={{ flex: 1 }}>Transcript · {takes.length} takes</span>
      </div>
      <div style={{ padding: "8px 10px 0" }}>
        <input
          className="input"
          placeholder="search phrases…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={{ fontSize: 12, padding: "5px 9px" }}
        />
      </div>
      <div className="tk-legend">
        <span><i style={{ background: "var(--accent)" }} /> kept</span>
        <span><i style={{ background: "var(--danger)" }} /> cut</span>
        <span><i style={{ background: "var(--warn)" }} /> partial</span>
      </div>
      <div className="panel-b">
        {takes.map((take) => {
          const vis = filter
            ? take.phrases.filter((p) => p.text.toLowerCase().includes(filter.toLowerCase()))
            : take.phrases;
          if (filter && !vis.length) return null;
          const isOpen = open[take.source] ?? (takes.length <= 4 || !!filter);
          return (
            <div className="tk-take" key={take.source}>
              <div
                className="tk-take-h"
                onClick={() => setOpen((o) => ({ ...o, [take.source]: !isOpen }))}
              >
                <span className="name">{take.source}</span>
                <span className="tag">{take.duration.toFixed(1)}s</span>
                <span className="tag">{take.phrases.length} phrases</span>
                <span className="dim mono" style={{ marginLeft: "auto", fontSize: 10 }}>
                  {isOpen ? "▾" : "▸"}
                </span>
              </div>
              {isOpen &&
                vis.map((p, i) => {
                  const cov = phraseCoverage(edl, take.source, p.start, p.end);
                  const cls = cov === "kept" ? "kept" : cov === "cut" ? "cut" : "";
                  return (
                    <div
                      key={i}
                      className={`tk-phrase ${cls}`}
                      style={cov === "partial" ? { borderLeftColor: "var(--warn)" } : undefined}
                      onClick={() => seekPhrase(take.source, p.start)}
                      title={cov === "cut" ? "not in the current cut" : "click to seek"}
                    >
                      <span className="t">
                        {p.start.toFixed(2)}–{p.end.toFixed(2)}
                      </span>
                      <span style={{ flex: 1 }}>{p.text}</span>
                      {cov === "cut" && edl && (
                        <button
                          className="btn small ghost"
                          title="add this phrase back into the cut"
                          onClick={(e) => {
                            e.stopPropagation();
                            keepPhrase(take.source, p.start, p.end, p.text);
                          }}
                        >
                          + keep
                        </button>
                      )}
                    </div>
                  );
                })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
