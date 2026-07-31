"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { StudioProvider, useStudio } from "./studio";
import TranscriptPanel from "./TranscriptPanel";
import PreviewPlayer from "./PreviewPlayer";
import Timeline from "./Timeline";
import Inspector from "./Inspector";
import AgentDock from "./AgentDock";
import MobileEditor from "./MobileEditor";

export default function Editor() {
  const params = useSearchParams();
  const dir = params.get("dir");
  if (!dir) {
    return (
      <div className="home">
        <p>
          No project selected. <Link href="/">Pick one →</Link>
        </p>
      </div>
    );
  }
  return (
    <StudioProvider dir={dir}>
      <EditorInner />
    </StudioProvider>
  );
}

function EditorInner() {
  const st = useStudio();
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 880px)");
    const apply = () => setIsMobile(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  if (st.loadError) {
    return (
      <div className="home">
        <p style={{ color: "var(--danger)" }}>{st.loadError}</p>
        <Link href="/">← back</Link>
      </div>
    );
  }

  if (isMobile) return <MobileEditor />;

  return (
    <div className="editor">
      <div className="ed-top">
        <Link href="/" className="wordmark" style={{ textDecoration: "none" }}>
          ⟵ video-use <span style={{ color: "var(--accent)" }}>studio</span>
        </Link>
        <span className="title">{st.proj?.name ?? "…"}</span>
        {st.proj?.missingSources && st.proj.missingSources.length > 0 && (
          <span className="tag danger" title={`EDL sources not found on disk: ${st.proj.missingSources.join(", ")} — fix paths in edl.json or move the files next to the project`}>
            {st.proj.missingSources.length} missing source{st.proj.missingSources.length > 1 ? "s" : ""}
          </span>
        )}
        {st.proj && !st.proj.hasEdit && <span className="tag warn">fresh folder — no edit/ yet</span>}
        {st.proj?.edl && (
          <span className="tag">
            grade: {typeof st.proj.edl.grade === "string" ? st.proj.edl.grade : "custom"}
          </span>
        )}
        {st.proj?.edl?.subtitles && <span className="tag accent">subs wired</span>}
        <span className="spacer" />
        <span className="dim mono path" title={st.dir}>
          <bdi>{st.dir}</bdi>
        </span>
      </div>

      <TranscriptPanel />

      <div className="ed-center">
        <PreviewPlayer />
        <Timeline />
      </div>

      <Inspector />

      <AgentDock />
    </div>
  );
}
