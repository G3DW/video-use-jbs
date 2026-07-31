"use client";

import { useEffect, useMemo, useRef } from "react";
import { useStudio } from "./studio";
import { mediaUrl } from "@/lib/client/api";
import { fmtTime, totalDuration } from "@/lib/client/timeline";

/**
 * Plays the newest render of the cut. Prefers final.mp4 → final_no_subs.mp4 →
 * preview.mp4 → base.mp4. Marks the render stale when edl.json is newer.
 */
export default function PreviewPlayer() {
  const st = useStudio();
  const videoRef = useRef<HTMLVideoElement>(null);
  const { proj, playerRel, setPlayerRel, seekReq, setPlayhead, playhead } = st;

  const renderChoices = useMemo(() => {
    const order = ["final.mp4", "final_no_subs.mp4", "preview.mp4", "draft.mp4", "base.mp4", "base_preview.mp4", "base_draft.mp4"];
    return (proj?.renders ?? [])
      .slice()
      .sort((a, b) => order.indexOf(a.name) - order.indexOf(b.name));
  }, [proj?.renders]);

  const active = useMemo(
    () => renderChoices.find((r) => r.rel === playerRel) ?? renderChoices[0] ?? null,
    [renderChoices, playerRel]
  );

  useEffect(() => {
    if (!playerRel && active) setPlayerRel(active.rel);
  }, [active, playerRel, setPlayerRel]);

  const stale =
    !!active && !!proj?.edlMtimeMs && proj.edlMtimeMs > active.mtimeMs + 1000;

  // external seeks
  useEffect(() => {
    if (seekReq && videoRef.current) {
      videoRef.current.currentTime = seekReq.t;
    }
  }, [seekReq]);

  const edlDur = totalDuration(proj?.edl ?? null);

  return (
    <div className="player-wrap">
      <div className="player-stage">
        {stale && (
          <span className="tag warn stale-badge" title="edl.json changed after this file was rendered">
            render is stale — re-render to see current cut
          </span>
        )}
        {active ? (
          <video
            key={active.rel}
            ref={videoRef}
            src={mediaUrl(st.dir, active.rel)}
            controls
            playsInline
            onTimeUpdate={(e) => setPlayhead(e.currentTarget.currentTime)}
          />
        ) : (
          <div className="no-media">
            no render yet — run a preview render from the console below,
            <br />
            or ask the agent to cut the footage first
          </div>
        )}
      </div>
      <div className="player-bar">
        <span className="time">
          {fmtTime(playhead)} / {fmtTime(edlDur || 0)}
        </span>
        {renderChoices.length > 1 && (
          <select
            className="input"
            style={{ width: "auto", padding: "4px 8px", fontSize: 12 }}
            value={active?.rel ?? ""}
            onChange={(e) => setPlayerRel(e.target.value)}
          >
            {renderChoices.map((r) => (
              <option key={r.rel} value={r.rel}>
                {r.name} ({(r.size / 1e6).toFixed(0)} MB)
              </option>
            ))}
          </select>
        )}
        <span className="spacer" style={{ flex: 1 }} />
        <button className="btn small" onClick={() => st.runJob("render_preview")}>
          Render preview
        </button>
        <button className="btn small accent" onClick={() => st.runJob("render_final")}>
          Render final
        </button>
      </div>
    </div>
  );
}
