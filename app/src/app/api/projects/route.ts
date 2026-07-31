import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { REPO_ROOT, VIDEO_EXTS, checkProjectDir, readConfig, rememberProject } from "@/lib/server/paths";

export const dynamic = "force-dynamic";

/** List recent projects + auto-discovered candidates inside the repo. */
export async function GET() {
  const cfg = readConfig();
  const recent = cfg.recentProjects.filter((d) => fs.existsSync(d));

  // Auto-discover: any dir in the repo root containing video files
  const discovered: string[] = [];
  try {
    for (const entry of fs.readdirSync(REPO_ROOT)) {
      const abs = path.join(REPO_ROOT, entry);
      if (entry.startsWith(".") || entry === "app" || entry === "node_modules") continue;
      try {
        if (!fs.statSync(abs).isDirectory()) continue;
        const hasVideo = fs
          .readdirSync(abs)
          .some((f) => VIDEO_EXTS.has(path.extname(f).toLowerCase()));
        if (hasVideo && !recent.includes(abs)) discovered.push(abs);
      } catch {}
    }
  } catch {}

  const describe = (dir: string) => {
    let nVideos = 0;
    let hasEdit = false;
    try {
      nVideos = fs.readdirSync(dir).filter((f) => VIDEO_EXTS.has(path.extname(f).toLowerCase())).length;
      hasEdit = fs.existsSync(path.join(dir, "edit"));
    } catch {}
    return { dir, name: path.basename(dir), nVideos, hasEdit };
  };

  return NextResponse.json({
    recent: recent.map(describe),
    discovered: discovered.map(describe),
  });
}

/** Validate + remember a project dir typed by the user. */
export async function POST(req: NextRequest) {
  try {
    const { dir } = await req.json();
    const abs = checkProjectDir(dir);
    rememberProject(abs);
    return NextResponse.json({ ok: true, dir: abs });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 400 });
  }
}
