import { NextRequest } from "next/server";
import fs from "fs";
import { checkProjectDir } from "@/lib/server/paths";
import { absSource, cacheDir } from "@/lib/server/project";
import { extractFrame, probeVideo } from "@/lib/server/ffmpeg";
import path from "path";
import { execFile } from "child_process";
import { promisify } from "util";
import { HELPERS_DIR, jobEnv, pythonBin } from "@/lib/server/paths";

const pexec = promisify(execFile);
const presetFilters = new Map<string, string>();

async function resolvePreset(name: string): Promise<string | undefined> {
  if (name === "none" || name === "auto") return undefined;
  if (presetFilters.has(name)) return presetFilters.get(name) || undefined;
  try {
    const { stdout } = await pexec(
      pythonBin(),
      [path.join(HELPERS_DIR, "grade.py"), "--print-preset", name],
      { env: jobEnv() }
    );
    const f = stdout.trim();
    presetFilters.set(name, f);
    return f || undefined;
  } catch {
    return undefined;
  }
}

export const dynamic = "force-dynamic";

/**
 * Single-frame JPEG from any project video, optionally with an ffmpeg filter
 * (grade preview) applied. Cached on disk. HDR sources are tonemapped so the
 * preview matches what render.py will produce.
 *
 * /api/frame?dir=...&path=<rel>&t=12.3&w=320&vf=<filter>
 */
export async function GET(req: NextRequest) {
  try {
    const q = req.nextUrl.searchParams;
    const dir = checkProjectDir(q.get("dir") ?? "");
    const rel = q.get("path") ?? "";
    const t = parseFloat(q.get("t") ?? "0");
    const w = q.get("w") ? parseInt(q.get("w")!, 10) : undefined;
    let vf = q.get("vf") ?? undefined;
    const preset = q.get("preset");
    if (!vf && preset) vf = await resolvePreset(preset);
    const abs = absSource(dir, rel);
    if (!fs.existsSync(abs)) throw new Error(`missing: ${rel}`);

    let hdr = false;
    try {
      hdr = (await probeVideo(abs)).hdr;
    } catch {}

    const out = await extractFrame({
      video: abs,
      t: isFinite(t) ? Math.max(0, t) : 0,
      vf,
      width: w,
      cacheDir: path.join(cacheDir(dir), "frames"),
      hdr,
    });
    return new Response(fs.readFileSync(out), {
      headers: { "Content-Type": "image/jpeg", "Cache-Control": "private, max-age=3600" },
    });
  } catch (err) {
    return new Response(String(err), { status: 500 });
  }
}
