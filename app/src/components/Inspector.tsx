"use client";

import { useEffect, useMemo, useState } from "react";
import { useStudio } from "./studio";
import { frameUrl, buildSubs, fetchEdlHistory, restoreEdl, mediaUrl } from "@/lib/client/api";
import { beatColor, fmtTime, outputSegments } from "@/lib/client/timeline";
import { DEFAULT_SUB_STYLE_CLIENT } from "./subdefaults";
import type { SubtitleStyle } from "@/lib/types";

const TABS = ["Cuts", "Grade", "Subtitles", "Animations", "Self-Eval", "History"] as const;
export type TabName = (typeof TABS)[number];

export default function Inspector({ initialTab }: { initialTab?: TabName }) {
  const [tab, setTab] = useState<TabName>(initialTab ?? "Cuts");
  return (
    <div className="panel ed-right">
      <div className="insp-tabs">
        {TABS.map((t) => (
          <button key={t} className={`insp-tab${t === tab ? " active" : ""}`} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>
      <div className="insp-body">
        {tab === "Cuts" && <CutsTab />}
        {tab === "Grade" && <GradeTab />}
        {tab === "Subtitles" && <SubtitlesTab />}
        {tab === "Animations" && <AnimationsTab />}
        {tab === "Self-Eval" && <EvalTab />}
        {tab === "History" && <HistoryTab />}
      </div>
    </div>
  );
}

/* ───────────────────────── Cuts ───────────────────────── */

export function CutsTab() {
  const st = useStudio();
  const segs = useMemo(() => outputSegments(st.proj?.edl ?? null), [st.proj?.edl]);

  if (!segs.length)
    return <div className="no-media">no cuts yet — the agent&apos;s proposed EDL will appear here, each with its reason</div>;

  const reject = (index: number) => {
    if (!confirm("Remove this cut from the EDL? (recoverable from History)")) return;
    st.updateEdl((edl) => {
      edl.ranges.splice(index, 1);
      return edl;
    });
    st.setSelection(null);
  };

  const nudge = (index: number, edge: "start" | "end", delta: number) => {
    st.updateEdl((edl) => {
      const r = edl.ranges[index];
      r[edge] = Math.max(0, Math.round((r[edge] + delta) * 1000) / 1000);
      if (r.end <= r.start) r.end = r.start + 0.1;
      return edl;
    });
  };

  const drill = async (index: number) => {
    const s = segs[index];
    await st.runJob("timeline_view", {
      source: s.source,
      start: Math.max(0, s.start - 1.5),
      end: s.end + 1.5,
    });
  };

  return (
    <>
      <div className="dim" style={{ fontSize: 11.5 }}>
        Every segment in the cut, in output order, with the editor&apos;s reason. Click to
        select + seek; reject removes it; drag its edges on the timeline (snaps to word
        boundaries).
      </div>
      {segs.map((s) => (
        <div
          key={s.index}
          className={`cut-card${st.selection === s.index ? " selected" : ""}`}
          onClick={() => {
            st.setSelection(s.index);
            st.seek(s.offset + 0.01);
          }}
        >
          <div className="row1">
            <span className="tag" style={{ color: beatColor(s.beat), borderColor: beatColor(s.beat) }}>
              {s.beat ?? "—"}
            </span>
            <span className="mono" style={{ fontSize: 11.5, fontWeight: 600 }}>{s.source}</span>
            <span className="times" style={{ marginLeft: "auto" }}>
              {s.start.toFixed(2)}–{s.end.toFixed(2)} · {s.dur.toFixed(2)}s
            </span>
          </div>
          {s.quote && <div className="quote">“{s.quote}”</div>}
          {s.reason && <div className="reason">{s.reason}</div>}
          <div className="times">out @ {fmtTime(s.offset)}</div>
          {st.selection === s.index && (
            <div className="actions" onClick={(e) => e.stopPropagation()}>
              <button className="btn small" onClick={() => nudge(s.index, "start", -0.1)}>⟨ in −.1</button>
              <button className="btn small" onClick={() => nudge(s.index, "start", 0.1)}>in +.1 ⟩</button>
              <button className="btn small" onClick={() => nudge(s.index, "end", -0.1)}>⟨ out −.1</button>
              <button className="btn small" onClick={() => nudge(s.index, "end", 0.1)}>out +.1 ⟩</button>
              <button className="btn small" title="filmstrip+waveform PNG around this cut (appears in Self-Eval)" onClick={() => drill(s.index)}>
                inspect
              </button>
              <button className="btn small danger" onClick={() => reject(s.index)}>reject</button>
            </div>
          )}
        </div>
      ))}
    </>
  );
}

/* ───────────────────────── Grade ───────────────────────── */

export function GradeTab() {
  const st = useStudio();
  const edl = st.proj?.edl ?? null;
  const [pending, setPending] = useState<string | null>(null);
  const [custom, setCustom] = useState("");
  const segs = useMemo(() => outputSegments(edl), [edl]);
  const current = edl?.grade ?? "none";
  const presets = st.proj?.gradePresets ?? [];

  const sel = st.selection != null && segs[st.selection] ? segs[st.selection] : segs[0];
  const srcRel = sel ? st.proj?.resolvedSources[sel.source] : null;
  const midT = sel ? (sel.start + sel.end) / 2 : 0;

  const shown = pending ?? (typeof current === "string" ? current : "custom");
  const isCustomShown = !presets.includes(shown) && shown !== "none" && shown !== "auto";

  const apply = (grade: string) => {
    st.updateEdl((edl) => {
      edl.grade = grade === "none" ? "none" : grade;
      return edl;
    });
    setPending(null);
  };

  if (!edl) return <div className="no-media">grade controls appear once an EDL exists</div>;

  return (
    <>
      <div className="dim" style={{ fontSize: 11.5 }}>
        Grade is baked per-segment at render time (changing it requires a re-render).
        Current: <b className="mono" style={{ color: "var(--accent)" }}>{typeof current === "string" ? current : "custom"}</b>
      </div>

      {srcRel && (
        <div className="grade-compare">
          <figure>
            <img src={frameUrl(st.dir, srcRel, midT, 480)} alt="original" />
            <figcaption>original · {sel?.source} @ {midT.toFixed(1)}s</figcaption>
          </figure>
          <figure>
            {shown === "none" || shown === "auto" || (isCustomShown && !custom) ? (
              <img src={frameUrl(st.dir, srcRel, midT, 480)} alt="preview" />
            ) : (
              <img
                src={
                  isCustomShown || shown === "custom"
                    ? frameUrl(st.dir, srcRel, midT, 480, custom || undefined)
                    : frameUrl(st.dir, srcRel, midT, 480, undefined, shown)
                }
                alt="preview"
              />
            )}
            <figcaption>
              {shown === "auto" ? "auto — computed per segment at render" : `preview · ${shown}`}
            </figcaption>
          </figure>
        </div>
      )}
      <div className="dim" style={{ fontSize: 10.5 }}>
        preview frame follows the selected segment — select a different cut to check skin tones elsewhere
      </div>

      <div className="preset-grid">
        {presets.map((p) => (
          <button
            key={p}
            className={`preset-card${shown === p ? " active" : ""}`}
            onClick={() => setPending(p)}
          >
            {p}
          </button>
        ))}
      </div>

      <div className="field">
        <label>custom ffmpeg filter</label>
        <textarea
          className="input"
          rows={2}
          placeholder="eq=contrast=1.08:saturation=1.05,curves=…"
          value={custom}
          onChange={(e) => {
            setCustom(e.target.value);
            setPending("custom");
          }}
        />
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <button
          className="btn accent"
          disabled={!pending}
          onClick={() => apply(pending === "custom" ? custom.trim() : pending!)}
        >
          Apply to EDL
        </button>
        {pending && (
          <button className="btn ghost" onClick={() => setPending(null)}>
            discard
          </button>
        )}
      </div>
    </>
  );
}

/* ───────────────────────── Subtitles ───────────────────────── */

export function SubtitlesTab() {
  const st = useStudio();
  const saved = st.proj?.subStyle;
  const [style, setStyle] = useState<SubtitleStyle>({ ...DEFAULT_SUB_STYLE_CLIENT, ...(saved ?? {}) });
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  useEffect(() => {
    if (saved) setStyle((s) => ({ ...s, ...saved }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [st.proj?.dir]);

  const edl = st.proj?.edl ?? null;
  const segs = useMemo(() => outputSegments(edl), [edl]);
  const sel = st.selection != null && segs[st.selection] ? segs[st.selection] : segs[0];
  const srcRel = sel ? st.proj?.resolvedSources[sel.source] : null;

  const sampleText = useMemo(() => {
    const take = st.proj?.takes.find((t) => t.source === sel?.source);
    const p = take?.phrases.find((p) => sel && p.start >= sel.start - 0.3);
    let text = p?.text ?? "your caption preview";
    const words = text.split(" ").slice(0, style.chunkMode === "two-word" ? 2 : 5);
    text = words.join(" ");
    return style.uppercase ? text.toUpperCase() : text;
  }, [st.proj?.takes, sel, style.chunkMode, style.uppercase]);

  const set = <K extends keyof SubtitleStyle>(k: K, v: SubtitleStyle[K]) =>
    setStyle((s) => ({ ...s, [k]: v }));

  const hasTranscripts = (st.proj?.transcribedSources?.length ?? 0) > 0;

  const build = async () => {
    setBusy(true);
    setNote(null);
    try {
      const r = await buildSubs(st.dir, style);
      if (r.error) throw new Error(r.error);
      setNote(
        style.enabled
          ? `master.ass written (${r.cueCount} cues) and wired into the EDL — subtitles burn in on the next render`
          : "subtitles disabled in the EDL"
      );
      st.refresh();
    } catch (err) {
      setNote(String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="dim" style={{ fontSize: 11.5 }}>
        Builds a standalone <span className="mono">master.ass</span> (style baked in — no
        force_style, per Session 3) with output-timeline offsets. Burned LAST at render
        (Hard Rule 1).
      </div>

      {srcRel && (
        <div style={{ position: "relative", borderRadius: 8, overflow: "hidden", border: "1px solid var(--line)", containerType: "inline-size" }}>
          <img src={frameUrl(st.dir, srcRel, sel ? (sel.start + sel.end) / 2 : 0, 480)} alt="frame" style={{ width: "100%", display: "block" }} />
          {style.enabled && (
            <div
              style={{
                position: "absolute",
                left: `${(100 - style.maxWidthPct) / 2}%`,
                right: `${(100 - style.maxWidthPct) / 2}%`,
                bottom: `${style.marginVPct}%`,
                textAlign: "center",
                fontFamily: style.fontFamily + ", sans-serif",
                fontWeight: style.bold ? 800 : 400,
                // sizePct is % of frame HEIGHT; container queries give us width (cqw)
                fontSize: `${(style.sizePct * ((sel && st.proj?.probes[sel.source] ? st.proj.probes[sel.source].height / Math.max(1, st.proj.probes[sel.source].width) : 0.5625))).toFixed(2)}cqw`,
                color: style.primaryColor,
                lineHeight: 1.25,
                textShadow: style.backdrop === "outline" ? "0 0 4px #000, 0 0 4px #000, 2px 2px 2px #000" : undefined,
              }}
            >
              <span
                style={
                  style.backdrop === "box"
                    ? { background: `rgba(0,0,0,${style.boxOpacity})`, padding: "0.15em 0.4em", boxDecorationBreak: "clone", WebkitBoxDecorationBreak: "clone" }
                    : undefined
                }
              >
                {sampleText}
              </span>
            </div>
          )}
        </div>
      )}

      <div className="field-row">
        <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13 }}>
          <input type="checkbox" checked={style.enabled} onChange={(e) => set("enabled", e.target.checked)} />
          burn subtitles into the render
        </label>
      </div>

      <div className="field-row">
        <div className="field">
          <label>font family</label>
          <input className="input" value={style.fontFamily} onChange={(e) => set("fontFamily", e.target.value)} />
        </div>
        <div className="field">
          <label>chunking</label>
          <select className="input" value={style.chunkMode} onChange={(e) => set("chunkMode", e.target.value as SubtitleStyle["chunkMode"])}>
            <option value="natural">natural (pause-aware)</option>
            <option value="two-word">2-word bold-overlay</option>
          </select>
        </div>
      </div>

      {(st.proj?.fonts?.length ?? 0) > 0 && (
        <div className="dim" style={{ fontSize: 10.5 }}>
          fonts in edit/fonts: {st.proj!.fonts.map((f) => f.split("/").pop()).join(", ")} — use the family name
        </div>
      )}

      <div className="field">
        <label>size · {style.sizePct.toFixed(1)}% of frame height</label>
        <input type="range" min={2} max={8} step={0.1} value={style.sizePct} onChange={(e) => set("sizePct", parseFloat(e.target.value))} />
      </div>
      <div className="field">
        <label>bottom margin · {style.marginVPct.toFixed(0)}% up from bottom (≥25% clears TikTok/Reels UI)</label>
        <input type="range" min={5} max={60} step={1} value={style.marginVPct} onChange={(e) => set("marginVPct", parseFloat(e.target.value))} />
      </div>
      <div className="field">
        <label>max width · {style.maxWidthPct.toFixed(0)}%</label>
        <input type="range" min={40} max={95} step={1} value={style.maxWidthPct} onChange={(e) => set("maxWidthPct", parseFloat(e.target.value))} />
      </div>

      <div className="field-row">
        <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13 }}>
          <input type="checkbox" checked={style.uppercase} onChange={(e) => set("uppercase", e.target.checked)} />
          UPPERCASE
        </label>
        <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13 }}>
          <input type="checkbox" checked={style.bold} onChange={(e) => set("bold", e.target.checked)} />
          bold
        </label>
        <div className="field">
          <label>backdrop</label>
          <select className="input" value={style.backdrop} onChange={(e) => set("backdrop", e.target.value as SubtitleStyle["backdrop"])}>
            <option value="box">opaque box</option>
            <option value="outline">outline only</option>
          </select>
        </div>
      </div>
      {style.backdrop === "box" && (
        <div className="field">
          <label>box opacity · {(style.boxOpacity * 100).toFixed(0)}%</label>
          <input type="range" min={0.2} max={1} step={0.05} value={style.boxOpacity} onChange={(e) => set("boxOpacity", parseFloat(e.target.value))} />
        </div>
      )}

      {!hasTranscripts && (
        <div className="tag warn">transcripts required — run Transcribe first</div>
      )}
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button className="btn accent" onClick={build} disabled={busy || !edl || !hasTranscripts}>
          {busy ? "building…" : "Build master.ass + save style"}
        </button>
      </div>
      {note && <div className="dim" style={{ fontSize: 11.5 }}>{note}</div>}
      {(st.proj?.subtitleFiles?.length ?? 0) > 0 && (
        <div className="dim mono" style={{ fontSize: 10.5 }}>
          existing: {st.proj!.subtitleFiles.join(", ")}
        </div>
      )}
    </>
  );
}

/* ───────────────────────── Animations ───────────────────────── */

export function AnimationsTab() {
  const st = useStudio();
  const edl = st.proj?.edl ?? null;
  const anims = st.proj?.animations ?? [];
  const [desc, setDesc] = useState("");
  const [engine, setEngine] = useState("auto");
  const [at, setAt] = useState("");

  const overlayFor = (render: string | null) =>
    (edl?.overlays ?? []).findIndex((o) => render && o.file.replace(/^\.\//, "") === render);

  const setOverlay = (render: string, field: "start_in_output" | "duration", value: number) => {
    st.updateEdl((edl) => {
      edl.overlays = edl.overlays ?? [];
      const i = edl.overlays.findIndex((o) => o.file === render);
      if (i === -1) edl.overlays.push({ file: render, start_in_output: 0, duration: 5, [field]: value });
      else edl.overlays[i][field] = value;
      return edl;
    });
  };

  const removeOverlay = (render: string) => {
    st.updateEdl((edl) => {
      edl.overlays = (edl.overlays ?? []).filter((o) => o.file !== render);
      return edl;
    });
  };

  const requestAnimation = () => {
    const prompt = `Build ONE new overlay animation for the current edit.

Spec from the user: ${desc}
Engine preference: ${engine === "auto" ? "your choice (HyperFrames / Remotion / Manim / PIL — pick per the skill's tool options)" : engine}
${at ? `Target placement in the output timeline: around ${at}s.` : "Propose the placement that fits the narration."}

Follow the skill's animation rules: create edit/animations/slot_<next-id>/, spawn a parallel sub-agent with a fully self-contained brief, render to render.mp4 (or render.webm for alpha), verify with ffprobe, then add the overlay entry to edl.json with the correct start_in_output and duration. Match the video's palette/brand as discussed — if unknown, propose a palette and wait for confirmation.`;
    st.sendAgent(prompt);
    setDesc("");
  };

  return (
    <>
      <div className="dim" style={{ fontSize: 11.5 }}>
        Animation slots under <span className="mono">edit/animations/</span>. Authoring is
        agent-driven (parallel sub-agents, one per slot); placement is editable here and
        on the overlay track.
      </div>

      {anims.length === 0 && <div className="no-media">no animation slots yet</div>}

      {anims.map((a) => {
        const oi = overlayFor(a.render);
        const overlay = oi >= 0 ? edl!.overlays![oi] : null;
        return (
          <div className="anim-card" key={a.id}>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span className="mono" style={{ fontWeight: 600, fontSize: 12 }}>{a.id}</span>
              {a.render ? <span className="tag ok">rendered</span> : <span className="tag warn">no render</span>}
              {overlay && <span className="tag accent">on timeline</span>}
            </div>
            {a.render && <video src={mediaUrl(st.dir, a.render)} controls muted playsInline />}
            {a.brief && (
              <details>
                <summary className="dim" style={{ fontSize: 11, cursor: "pointer" }}>brief</summary>
                <pre style={{ whiteSpace: "pre-wrap", fontSize: 10.5, color: "var(--dim)" }}>{a.brief}</pre>
              </details>
            )}
            {a.render && (
              <div className="field-row">
                <div className="field">
                  <label>start in output (s)</label>
                  <input
                    className="input" type="number" step={0.1}
                    value={overlay?.start_in_output ?? ""}
                    placeholder="—"
                    onChange={(e) => setOverlay(a.render!, "start_in_output", parseFloat(e.target.value) || 0)}
                  />
                </div>
                <div className="field">
                  <label>duration (s)</label>
                  <input
                    className="input" type="number" step={0.1}
                    value={overlay?.duration ?? ""}
                    placeholder="—"
                    onChange={(e) => setOverlay(a.render!, "duration", parseFloat(e.target.value) || 0)}
                  />
                </div>
                {overlay && (
                  <button className="btn small danger" onClick={() => removeOverlay(a.render!)} style={{ alignSelf: "flex-end" }}>
                    remove
                  </button>
                )}
              </div>
            )}
          </div>
        );
      })}

      <div className="sec-label">Request a new animation</div>
      <div className="field">
        <label>what should it show?</label>
        <textarea className="input" rows={3} placeholder="e.g. a counter card revealing '90% wasted' synced to the payoff word…" value={desc} onChange={(e) => setDesc(e.target.value)} />
      </div>
      <div className="field-row">
        <div className="field">
          <label>engine</label>
          <select className="input" value={engine} onChange={(e) => setEngine(e.target.value)}>
            <option value="auto">agent&apos;s choice</option>
            <option value="HyperFrames">HyperFrames (HTML/GSAP)</option>
            <option value="Remotion">Remotion (React)</option>
            <option value="Manim">Manim (diagrams/math)</option>
            <option value="PIL">PIL + ffmpeg (simple cards)</option>
          </select>
        </div>
        <div className="field">
          <label>at output time (s, optional)</label>
          <input className="input" value={at} onChange={(e) => setAt(e.target.value)} placeholder="auto" />
        </div>
      </div>
      <button className="btn accent" disabled={!desc.trim() || st.agentRunning} onClick={requestAnimation}>
        Send to agent
      </button>
    </>
  );
}

/* ───────────────────────── Self-Eval ───────────────────────── */

export function EvalTab() {
  const st = useStudio();
  const [zoom, setZoom] = useState<string | null>(null);
  const imgs = st.proj?.verifyImages ?? [];

  const runSelfEval = () => {
    st.sendAgent(
      `Run the full self-eval pass (skill step 7) on the newest rendered output in edit/: run timeline_view on the RENDERED file at every cut boundary (±1.5s), check for visual discontinuities, waveform spikes/audio pops, hidden subtitles, misaligned overlays; sample first 2s, last 2s and 2–3 midpoints for grade consistency and subtitle readability; verify duration with ffprobe against the EDL. Save the check images into edit/verify/ and report pass/fail per boundary with fixes if needed (cap 3 passes).`
    );
  };

  return (
    <>
      <div className="dim" style={{ fontSize: 11.5 }}>
        The skill&apos;s self-eval loop, visible: boundary checks from{" "}
        <span className="mono">edit/verify/</span>. Run it after any render — the agent
        reports pass/fail in the chat and drops its check images here.
      </div>
      <button className="btn accent" onClick={runSelfEval} disabled={st.agentRunning}>
        Run self-eval on latest render
      </button>
      {imgs.length === 0 && <div className="no-media">no verify images yet</div>}
      <div className="verify-grid">
        {imgs.map((rel) => (
          <figure key={rel}>
            <img src={mediaUrl(st.dir, rel)} alt={rel} onClick={() => setZoom(rel)} loading="lazy" />
            <figcaption>{rel.replace("edit/verify/", "")}</figcaption>
          </figure>
        ))}
      </div>
      {zoom && (
        <div className="modal-back" onClick={() => setZoom(null)}>
          <img src={mediaUrl(st.dir, zoom)} alt={zoom} />
        </div>
      )}
    </>
  );
}

/* ───────────────────────── History ───────────────────────── */

export function HistoryTab() {
  const st = useStudio();
  const [hist, setHist] = useState<string[]>([]);
  useEffect(() => {
    fetchEdlHistory(st.dir).then(setHist).catch(() => {});
  }, [st.dir, st.proj?.edlMtimeMs]);

  const restore = async (name: string) => {
    if (!confirm(`Restore ${name}? Current EDL is backed up first.`)) return;
    await restoreEdl(st.dir, name);
    st.refresh();
  };

  return (
    <>
      <div className="sec-label">project.md — session memory</div>
      {(st.proj?.sessions ?? []).length === 0 && <div className="no-media">no project.md yet</div>}
      {(st.proj?.sessions ?? []).map((s, i) => (
        <div className="session-card" key={i}>
          <h4>{s.title}</h4>
          <pre>{s.body}</pre>
        </div>
      ))}
      <div className="sec-label">EDL versions</div>
      {hist.length === 0 && <div className="dim" style={{ fontSize: 11.5 }}>no saved versions yet — every UI/agent edit creates one</div>}
      {hist.map((h) => (
        <div key={h} style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className="mono" style={{ fontSize: 11, flex: 1 }}>{h}</span>
          <button className="btn small" onClick={() => restore(h)}>restore</button>
        </div>
      ))}
    </>
  );
}
