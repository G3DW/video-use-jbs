"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface ProjDesc {
  dir: string;
  name: string;
  nVideos: number;
  hasEdit: boolean;
}

export default function Home() {
  const router = useRouter();
  const [recent, setRecent] = useState<ProjDesc[]>([]);
  const [discovered, setDiscovered] = useState<ProjDesc[]>([]);
  const [manual, setManual] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/projects")
      .then((r) => r.json())
      .then((j) => {
        setRecent(j.recent ?? []);
        setDiscovered(j.discovered ?? []);
      })
      .catch(() => {});
  }, []);

  const open = (dir: string) => router.push(`/edit?dir=${encodeURIComponent(dir)}`);

  const openManual = async () => {
    setError(null);
    const r = await fetch("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dir: manual.trim() }),
    });
    const j = await r.json();
    if (j.ok) open(j.dir);
    else setError(j.error);
  };

  const Card = ({ p }: { p: ProjDesc }) => (
    <button className="proj-card" onClick={() => open(p.dir)}>
      <span className="name">{p.name}</span>
      <span className="meta">
        {p.nVideos} source{p.nVideos === 1 ? "" : "s"}
        {p.hasEdit ? " · edit session" : " · fresh"}
      </span>
      <span className="meta faint" title={p.dir}>
        <bdi>{p.dir}</bdi>
      </span>
    </button>
  );

  return (
    <main className="home">
      <div>
        <div className="wordmark">joeBuilds systems</div>
        <h1>
          video-use <span className="brand">studio</span>
        </h1>
        <p className="dim" style={{ maxWidth: 560 }}>
          The full video-use pipeline — transcripts, cuts with reasons, timeline, grade,
          subtitles, animations, self-eval — with the agent visible instead of scrolling
          terminal text.
        </p>
      </div>

      {recent.length > 0 && (
        <section style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div className="sec-label">Recent projects</div>
          <div className="proj-grid">
            {recent.map((p) => (
              <Card key={p.dir} p={p} />
            ))}
          </div>
        </section>
      )}

      {discovered.length > 0 && (
        <section style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div className="sec-label">Found in the video-use repo</div>
          <div className="proj-grid">
            {discovered.map((p) => (
              <Card key={p.dir} p={p} />
            ))}
          </div>
        </section>
      )}

      <section style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div className="sec-label">Open a folder by path</div>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            className="input"
            placeholder="/path/to/your/footage-folder"
            value={manual}
            onChange={(e) => setManual(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && openManual()}
          />
          <button className="btn accent" onClick={openManual} disabled={!manual.trim()}>
            Open
          </button>
        </div>
        {error && <div style={{ color: "var(--danger)", fontSize: 12 }}>{error}</div>}
      </section>
    </main>
  );
}
