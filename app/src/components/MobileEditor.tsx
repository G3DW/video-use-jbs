"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useStudio } from "./studio";
import { frameUrl, mediaUrl } from "@/lib/client/api";
import { fmtClock, outputSegments, snapToWord, totalDuration } from "@/lib/client/timeline";
import { CutsTab, GradeTab, SubtitlesTab, AnimationsTab, EvalTab } from "./Inspector";
import { EventRow } from "./AgentDock";
import type { Edl } from "@/lib/types";

type Sheet = "cuts" | "grade" | "subs" | "anim" | "eval" | "chat" | null;

/**
 * TikTok-style phone layout: full-height preview, horizontal filmstrip with
 * trim handles on the selected clip, bottom sheet for everything else.
 */
export default function MobileEditor() {
  const st = useStudio();
  const [sheet, setSheet] = useState<Sheet>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const edl = st.draftEdl ?? st.proj?.edl ?? null;
  const segs = useMemo(() => outputSegments(edl), [edl]);
  const total = totalDuration(edl);

  const active = st.proj?.renders?.[0] ?? null;
  const activeSorted = useMemo(() => {
    const order = ["final.mp4", "final_no_subs.mp4", "preview.mp4", "draft.mp4", "base.mp4"];
    return (st.proj?.renders ?? []).slice().sort((a, b) => order.indexOf(a.name) - order.indexOf(b.name))[0] ?? active;
  }, [st.proj?.renders, active]);

  useEffect(() => {
    if (st.seekReq && videoRef.current) videoRef.current.currentTime = st.seekReq.t;
  }, [st.seekReq]);

  // filmstrip trim drag
  const PPS = 6; // px per second in the strip
  const drag = useRef<{ index: number; edge: "start" | "end"; startX: number; orig: number } | null>(null);

  const beginDrag = useCallback(
    (index: number, edge: "start" | "end") => (e: React.PointerEvent) => {
      e.stopPropagation();
      if (!edl) return;
      drag.current = { index, edge, startX: e.clientX, orig: edl.ranges[index][edge] };
      st.getWords(edl.ranges[index].source).catch(() => {});
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    },
    [edl, st]
  );

  const onMove = useCallback(
    (e: React.PointerEvent) => {
      const d = drag.current;
      if (!d || !st.proj?.edl) return;
      const delta = (e.clientX - d.startX) / PPS;
      const next = structuredClone(st.proj.edl) as Edl;
      const r = next.ranges[d.index];
      if (d.edge === "start") r.start = Math.max(0, Math.min(d.orig + delta, r.end - 0.15));
      else r.end = Math.max(r.start + 0.15, d.orig + delta);
      st.setDraftEdl(next);
    },
    [st]
  );

  const endDrag = useCallback(async () => {
    const d = drag.current;
    drag.current = null;
    if (!d || !st.draftEdl) return;
    const next = structuredClone(st.draftEdl) as Edl;
    const r = next.ranges[d.index];
    try {
      const words = await st.getWords(r.source);
      if (d.edge === "start") r.start = Math.min(snapToWord(words, r.start, "start"), r.end - 0.1);
      else r.end = Math.max(snapToWord(words, r.end, "end"), r.start + 0.1);
    } catch {}
    st.setDraftEdl(next);
    setTimeout(() => st.commitDraft(), 0);
  }, [st]);

  const subStyle = st.proj?.subStyle;

  return (
    <div className="m-editor">
      <div className="m-stage">
        <div className="m-topbar">
          <Link href="/" style={{ color: "#fff", textDecoration: "none", fontSize: 18 }}>‹</Link>
          <span className="title">{st.proj?.name}</span>
          {st.agentRunning && <span className="running-dot" />}
          <span className="tag" style={{ background: "rgba(0,0,0,0.4)" }}>
            {segs.length} cuts · {fmtClock(total)}
          </span>
        </div>
        {activeSorted ? (
          <video
            ref={videoRef}
            src={mediaUrl(st.dir, activeSorted.rel)}
            controls
            playsInline
            onTimeUpdate={(e) => st.setPlayhead(e.currentTarget.currentTime)}
          />
        ) : (
          <div className="no-media">no render yet — open Chat and ask for a cut</div>
        )}
      </div>

      <div className="m-filmstrip" onPointerMove={onMove} onPointerUp={endDrag}>
        <div className="m-strip-scroll">
          {segs.map((s) => {
            const rel = st.proj?.resolvedSources[s.source];
            const selected = st.selection === s.index;
            return (
              <div
                key={s.index}
                className={`m-clip${selected ? " selected" : ""}`}
                style={{
                  width: Math.max(26, s.dur * PPS),
                  backgroundImage: rel ? `url(${frameUrl(st.dir, rel, (s.start + s.end) / 2, 120)})` : undefined,
                }}
                onClick={() => {
                  st.setSelection(selected ? null : s.index);
                  st.seek(s.offset + 0.01);
                }}
              >
                <span className="dur">{s.dur.toFixed(1)}s</span>
                {selected && (
                  <>
                    <div className="m-trim l" onPointerDown={beginDrag(s.index, "start")} />
                    <div className="m-trim r" onPointerDown={beginDrag(s.index, "end")} />
                  </>
                )}
              </div>
            );
          })}
          {segs.length === 0 && <div className="no-media" style={{ padding: 8 }}>timeline appears after the first cut</div>}
        </div>
      </div>

      <div className="m-tabbar">
        {(
          [
            ["cuts", "Cuts"],
            ["grade", "Grade"],
            ["subs", "Subs"],
            ["anim", "Anim"],
            ["eval", "Eval"],
            ["chat", "Chat"],
          ] as [Sheet, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            className={`m-tab${sheet === key ? " active" : ""}`}
            onClick={() => setSheet(sheet === key ? null : key)}
          >
            {label}
            {key === "chat" && st.agentRunning ? " ●" : ""}
          </button>
        ))}
      </div>

      {sheet && (
        <div className="m-sheet">
          <div className="m-sheet-h">
            <span className="sec-label" style={{ flex: 1 }}>{sheet}</span>
            <button className="btn small ghost" onClick={() => setSheet(null)}>close</button>
          </div>
          <div className="m-sheet-b">
            {sheet === "cuts" && <CutsTab />}
            {sheet === "grade" && <GradeTab />}
            {sheet === "subs" && <SubtitlesTab />}
            {sheet === "anim" && <AnimationsTab />}
            {sheet === "eval" && <EvalTab />}
            {sheet === "chat" && <MobileChat />}
          </div>
        </div>
      )}
    </div>
  );
}

function MobileChat() {
  const st = useStudio();
  const [text, setText] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [st.agentEvents.length]);

  const send = async (t?: string) => {
    const msg = (t ?? text).trim();
    if (!msg) return;
    setText("");
    try {
      await st.sendAgent(msg);
    } catch (err) {
      alert(String(err));
    }
  };

  return (
    <>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {st.agentEvents
          .filter((e) => e.type !== "tool_use" && e.type !== "tool_result")
          .slice(-60)
          .map((ev, i) => (
            <EventRow key={i} ev={ev} onApprove={() => send("Approved — proceed with this strategy.")} onRevise={() => {}} />
          ))}
        <div ref={endRef} />
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          className="input"
          placeholder={st.agentRunning ? "agent working…" : "tell the editor…"}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          disabled={st.agentRunning}
        />
        <button className="btn accent" onClick={() => send()} disabled={st.agentRunning || !text.trim()}>
          Send
        </button>
      </div>
      {st.agentRunning && (
        <button className="btn small danger" onClick={() => st.interruptAgent()}>stop agent</button>
      )}
    </>
  );
}
