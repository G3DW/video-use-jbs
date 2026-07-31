"use client";

import { useEffect, useRef, useState } from "react";
import { useStudio } from "./studio";
import type { AgentEvent } from "@/lib/types";

/** Chat + live step console + job progress. The terminal, replaced. */
export default function AgentDock() {
  const st = useStudio();
  const [text, setText] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showSteps, setShowSteps] = useState(true);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [st.agentEvents.length, st.agentRunning]);

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

  const visible = st.agentEvents.filter(
    (e) => showSteps || (e.type !== "tool_use" && e.type !== "tool_result")
  );

  return (
    <div className="panel ed-dock">
      <div className="dock">
        <div className="dock-chat">
          <div className="panel-h">
            <span className="sec-label" style={{ flex: 1 }}>Agent</span>
            {st.agentRunning && (
              <>
                <span className="running-dot" />
                <span className="dim mono" style={{ fontSize: 10 }}>working</span>
                <button className="btn small danger" onClick={() => st.interruptAgent()}>stop</button>
              </>
            )}
            <label className="dim mono" style={{ fontSize: 10, display: "flex", gap: 5, alignItems: "center" }}>
              <input type="checkbox" checked={showSteps} onChange={(e) => setShowSteps(e.target.checked)} />
              steps
            </label>
            <button className="btn small ghost" title="Start a fresh agent session" onClick={() => confirm("Clear the conversation and start a new agent session?") && st.resetAgent()}>
              new session
            </button>
          </div>
          <div className="chat-scroll" ref={scrollRef}>
            {visible.length === 0 && (
              <div className="no-media" style={{ margin: "auto" }}>
                Talk to the editor agent — &quot;edit these into a launch video&quot;,
                &quot;tighten the demo section&quot;, &quot;add subtitles&quot;…
                <br />
                Same brain as the terminal, every step visible.
              </div>
            )}
            {visible.map((ev, i) => (
              <EventRow key={i} ev={ev} onApprove={() => send("Approved — proceed with this strategy.")} onRevise={() => document.getElementById("agent-input")?.focus()} />
            ))}
          </div>
          <div className="chat-inputbar">
            <textarea
              id="agent-input"
              placeholder={st.agentRunning ? "agent is working — you can queue a message after it finishes" : "tell the editor what you want…"}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              disabled={st.agentRunning}
            />
            <button className="btn accent" onClick={() => send()} disabled={st.agentRunning || !text.trim()}>
              Send
            </button>
          </div>
        </div>

        <div className="dock-side">
          <div className="panel-h">
            <span className="sec-label" style={{ flex: 1 }}>Pipeline</span>
          </div>
          <div className="quick-actions">
            <button className="btn small" onClick={() => st.runJob("transcribe")} title="transcribe_batch.py — word-level Scribe, cached per source">
              Transcribe
            </button>
            <button className="btn small" onClick={() => st.runJob("pack")} title="pack_transcripts.py → takes_packed.md">
              Pack
            </button>
            <button className="btn small" onClick={() => st.runJob("render_draft")} title="720p ultrafast — cut-point check">
              Draft
            </button>
            <button className="btn small" onClick={() => st.runJob("render_preview")} title="1080p medium — evaluable">
              Preview
            </button>
            <button className="btn small accent" onClick={() => st.runJob("render_final")}>
              Final
            </button>
          </div>
          <div className="panel-b">
            {st.jobs.length === 0 && (
              <div className="no-media">helper runs show here with live progress</div>
            )}
            {st.jobs.map((j) => (
              <div className="job-card" key={j.id}>
                <div className="row">
                  <span style={{ flex: 1, fontWeight: 600 }}>{j.label}</span>
                  {j.status === "running" ? (
                    <>
                      <span className="running-dot" />
                      <button className="btn small ghost" onClick={() => st.killJob(j.id)}>✕</button>
                    </>
                  ) : j.status === "done" ? (
                    <span className="tag ok">done</span>
                  ) : (
                    <span className="tag danger" title={j.error}>error</span>
                  )}
                </div>
                {j.progress && (
                  <div className="job-bar">
                    <i style={{ width: `${Math.min(100, (j.progress.done / j.progress.total) * 100)}%` }} />
                  </div>
                )}
                <div className="job-log" title={j.lines.slice(-8).join("\n")}>
                  {j.lines[j.lines.length - 1] ?? "…"}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function EventRow({
  ev,
  onApprove,
  onRevise,
}: {
  ev: AgentEvent;
  onApprove: () => void;
  onRevise: () => void;
}) {
  if (ev.type === "user_text") return <div className="msg user">{ev.text}</div>;
  if (ev.type === "assistant_text") return <div className="msg assistant">{ev.text}</div>;
  if (ev.type === "strategy")
    return (
      <div className="strategy-card">
        <span className="head">Proposed strategy — Hard Rule 11: nothing is cut until you approve</span>
        <div className="body">{ev.text}</div>
        <div className="actions">
          <button className="btn accent" onClick={onApprove}>Approve</button>
          <button className="btn" onClick={onRevise}>Revise…</button>
        </div>
      </div>
    );
  if (ev.type === "tool_use")
    return (
      <div className="msg step">
        <span className="tool">▸ {ev.name}</span> {ev.summary}
      </div>
    );
  if (ev.type === "tool_result")
    return (
      <div className={`msg step${ev.isError ? " err" : ""}`}>
        {ev.isError ? "✗" : "·"} {ev.summary || "(ok)"}
      </div>
    );
  if (ev.type === "result")
    return (
      <div className="msg step">
        — turn {ev.subtype}
        {ev.costUsd != null ? ` · $${ev.costUsd.toFixed(2)}` : ""}
      </div>
    );
  if (ev.type === "error") return <div className="msg step err">✗ {ev.message}</div>;
  return null;
}
