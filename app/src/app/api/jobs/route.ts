import { NextRequest, NextResponse } from "next/server";
import path from "path";
import { HELPERS_DIR, checkProjectDir, jobEnv, pythonBin } from "@/lib/server/paths";
import { absSource, loadProject } from "@/lib/server/project";
import { killJob, listJobs, startJob } from "@/lib/server/jobs";
import { writeSubtitles } from "@/lib/server/subs";
import type { SubtitleStyle } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json({ jobs: listJobs() });
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const dir = checkProjectDir(body.dir);
    const kind = body.kind as string;
    const py = pythonBin();
    const env = jobEnv();
    const editDir = path.join(dir, "edit");
    const edlPath = path.join(editDir, "edl.json");

    if (body.kill) {
      return NextResponse.json({ ok: killJob(body.kill) });
    }

    if (kind === "render_final" || kind === "render_preview" || kind === "render_draft") {
      const outName = kind === "render_final" ? "final.mp4" : kind === "render_preview" ? "preview.mp4" : "draft.mp4";
      const args = [path.join(HELPERS_DIR, "render.py"), edlPath, "-o", path.join(editDir, outName)];
      if (kind === "render_preview") args.push("--preview");
      if (kind === "render_draft") args.push("--draft");
      if (body.noSubtitles) args.push("--no-subtitles");
      const job = startJob({
        kind: kind as "render_final",
        label: kind === "render_final" ? "Render final" : kind === "render_preview" ? "Render preview" : "Render draft",
        cmd: py,
        args,
        cwd: dir,
        env,
      });
      return NextResponse.json({ job });
    }

    if (kind === "transcribe") {
      const job = startJob({
        kind: "transcribe",
        label: "Transcribe sources",
        cmd: py,
        args: [path.join(HELPERS_DIR, "transcribe_batch.py"), dir],
        cwd: dir,
        env,
      });
      return NextResponse.json({ job });
    }

    if (kind === "pack") {
      const job = startJob({
        kind: "pack",
        label: "Pack transcripts",
        cmd: py,
        args: [path.join(HELPERS_DIR, "pack_transcripts.py"), "--edit-dir", editDir],
        cwd: dir,
        env,
      });
      return NextResponse.json({ job });
    }

    if (kind === "timeline_view") {
      // body.source is a source name or rel path; body.start/end seconds
      const state = await loadProject(dir);
      const rel = state.resolvedSources[body.source] ?? body.source;
      const abs = absSource(dir, rel);
      const start = Number(body.start) || 0;
      const end = Number(body.end) || start + 3;
      const outRel = `edit/verify/studio_${String(body.source).replace(/[^\w.-]/g, "")}_${start.toFixed(2)}-${end.toFixed(2)}.png`;
      const args = [
        path.join(HELPERS_DIR, "timeline_view.py"),
        abs,
        String(start),
        String(end),
        "-o",
        path.join(dir, outRel),
      ];
      const tr = path.join(editDir, "transcripts", `${body.source}.json`);
      const fs = await import("fs");
      if (fs.existsSync(tr)) args.push("--transcript", tr);
      const job = startJob({
        kind: "timeline_view",
        label: `Timeline view ${body.source} ${start.toFixed(1)}–${end.toFixed(1)}s`,
        cmd: py,
        args,
        cwd: dir,
        env,
      });
      return NextResponse.json({ job, output: outRel });
    }

    if (kind === "build_subs") {
      // Synchronous — pure TS, fast.
      const state = await loadProject(dir);
      if (!state.edl) throw new Error("no edl.json yet");
      const style = body.style as SubtitleStyle;
      // Frame size from the first source's probe (portrait vs landscape)
      const firstSrc = state.edl.ranges[0]?.source;
      const probe = firstSrc ? state.probes[firstSrc] : null;
      const portrait = probe ? probe.height > probe.width : false;
      const frameW = portrait ? 1080 : 1920;
      const frameH = portrait ? 1920 : 1080;
      const { cueCount } = writeSubtitles({ dir, edl: state.edl, style, frameW, frameH });
      // point the EDL at master.ass (or clear it)
      const edl = state.edl;
      edl.subtitles = style.enabled ? "master.ass" : null;
      const { saveEdl } = await import("@/lib/server/project");
      saveEdl(dir, edl);
      return NextResponse.json({ ok: true, cueCount });
    }

    throw new Error(`unknown job kind: ${kind}`);
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 400 });
  }
}
