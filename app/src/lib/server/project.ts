import fs from "fs";
import path from "path";
import { execFile } from "child_process";
import { promisify } from "util";
import {
  HELPERS_DIR,
  VIDEO_EXTS,
  pythonBin,
  jobEnv,
  safeJoin,
} from "./paths";
import { probeVideo } from "./ffmpeg";
import type {
  AnimationSlot,
  Edl,
  ProjectSession,
  ProjectState,
  SourceProbe,
  SubtitleStyle,
  Take,
  WordEntry,
} from "../types";

const pexec = promisify(execFile);

export const DEFAULT_SUB_STYLE: SubtitleStyle = {
  enabled: false,
  fontFamily: "Helvetica",
  fontFile: null,
  sizePct: 4.2,
  bold: true,
  uppercase: true,
  chunkMode: "natural",
  marginVPct: 30,
  maxWidthPct: 70,
  backdrop: "box",
  primaryColor: "#FFFFFF",
  outlineColor: "#000000",
  boxOpacity: 0.65,
};

function editDir(dir: string) {
  return path.join(dir, "edit");
}

export function cacheDir(dir: string) {
  return path.join(editDir(dir), ".studio_cache");
}

// ---------- takes_packed.md parser ----------

export function parseTakesPacked(text: string): Take[] {
  const takes: Take[] = [];
  let cur: Take | null = null;
  for (const line of text.split("\n")) {
    const h = line.match(/^## (\S+)\s+\(duration:\s*([\d.]+)s/);
    if (h) {
      cur = { source: h[1], duration: parseFloat(h[2]), phrases: [] };
      takes.push(cur);
      continue;
    }
    const p = line.match(/^\s+\[(\d+\.\d+)-(\d+\.\d+)\]\s+(\S+)\s+(.*)$/);
    if (p && cur) {
      cur.phrases.push({
        start: parseFloat(p[1]),
        end: parseFloat(p[2]),
        speaker: p[3],
        text: p[4],
      });
    }
  }
  return takes;
}

// ---------- project.md sessions ----------

function parseSessions(md: string): ProjectSession[] {
  const out: ProjectSession[] = [];
  const parts = md.split(/^## /m).filter((s) => s.trim());
  for (const part of parts) {
    const nl = part.indexOf("\n");
    out.push({
      title: nl === -1 ? part.trim() : part.slice(0, nl).trim(),
      body: nl === -1 ? "" : part.slice(nl + 1).trim(),
    });
  }
  return out;
}

// ---------- source resolution ----------

/**
 * EDL source paths are often stale absolute paths (drive moved, machine changed).
 * Resolve each to a file that actually exists: exact path → project-root basename match.
 */
export function resolveSources(edl: Edl, dir: string) {
  const resolved: Record<string, string> = {};
  const missing: string[] = [];
  for (const [name, p] of Object.entries(edl.sources)) {
    if (fs.existsSync(p)) {
      resolved[name] = path.relative(dir, p).startsWith("..") ? p : path.relative(dir, p);
      continue;
    }
    const base = path.basename(p);
    const local = path.join(dir, base);
    if (fs.existsSync(local)) {
      resolved[name] = base;
      continue;
    }
    // try any extension variant of the source name
    const hit = fs
      .readdirSync(dir)
      .find((f) => path.parse(f).name === name && VIDEO_EXTS.has(path.extname(f).toLowerCase()));
    if (hit) resolved[name] = hit;
    else missing.push(name);
  }
  return { resolved, missing };
}

export function absSource(dir: string, relOrAbs: string): string {
  return path.isAbsolute(relOrAbs) ? relOrAbs : safeJoin(dir, relOrAbs);
}

// ---------- probes (cached) ----------

async function loadProbes(dir: string, files: Record<string, string>): Promise<Record<string, SourceProbe>> {
  const cd = cacheDir(dir);
  const cachePath = path.join(cd, "probes_v2.json"); // v2: rotation-aware w/h
  let cache: Record<string, SourceProbe & { mtimeMs?: number }> = {};
  try {
    cache = JSON.parse(fs.readFileSync(cachePath, "utf8"));
  } catch {}
  const out: Record<string, SourceProbe> = {};
  let dirty = false;
  await Promise.all(
    Object.entries(files).map(async ([name, rel]) => {
      const abs = absSource(dir, rel);
      let st: fs.Stats;
      try {
        st = fs.statSync(abs);
      } catch {
        return;
      }
      const c = cache[name];
      if (c && c.mtimeMs === st.mtimeMs) {
        out[name] = c;
        return;
      }
      try {
        const p = await probeVideo(abs);
        out[name] = p;
        cache[name] = { ...p, mtimeMs: st.mtimeMs };
        dirty = true;
      } catch {}
    })
  );
  if (dirty) {
    fs.mkdirSync(cd, { recursive: true });
    fs.writeFileSync(cachePath, JSON.stringify(cache, null, 1));
  }
  return out;
}

// ---------- grade presets ----------

let presetCache: string[] | null = null;
export async function gradePresets(): Promise<string[]> {
  if (presetCache) return presetCache;
  try {
    const { stdout } = await pexec(pythonBin(), [path.join(HELPERS_DIR, "grade.py"), "--list-presets"], {
      env: jobEnv(),
    });
    const names = [...stdout.matchAll(/^\s*(\w[\w-]*)\s*:/gm)].map((m) => m[1]);
    if (names.length) presetCache = names;
  } catch {}
  if (!presetCache) presetCache = ["none", "subtle", "neutral_punch", "warm_cinematic"];
  if (!presetCache.includes("auto")) presetCache = [...presetCache, "auto"];
  return presetCache;
}

// ---------- word-level transcript access ----------

export function loadWords(dir: string, source: string): WordEntry[] {
  const p = path.join(editDir(dir), "transcripts", `${source}.json`);
  const j = JSON.parse(fs.readFileSync(p, "utf8"));
  const words: WordEntry[] = [];
  for (const w of j.words ?? []) {
    if (w.type !== "word" || w.start == null || w.end == null) continue;
    words.push({ t: String(w.text ?? "").trim(), s: w.start, e: w.end });
  }
  return words;
}

// ---------- main loader ----------

export async function loadProject(dir: string): Promise<ProjectState> {
  const ed = editDir(dir);
  const hasEdit = fs.existsSync(ed);

  const sourceFiles = fs
    .readdirSync(dir)
    .filter((f) => VIDEO_EXTS.has(path.extname(f).toLowerCase()))
    .sort();

  let edl: Edl | null = null;
  let edlMtimeMs: number | null = null;
  const edlPath = path.join(ed, "edl.json");
  if (fs.existsSync(edlPath)) {
    try {
      edl = JSON.parse(fs.readFileSync(edlPath, "utf8"));
      edlMtimeMs = fs.statSync(edlPath).mtimeMs;
    } catch {}
  }

  let resolvedSources: Record<string, string> = {};
  let missingSources: string[] = [];
  if (edl) {
    const r = resolveSources(edl, dir);
    resolvedSources = r.resolved;
    missingSources = r.missing;
  } else {
    for (const f of sourceFiles) resolvedSources[path.parse(f).name] = f;
  }

  let takes: Take[] = [];
  const takesPath = path.join(ed, "takes_packed.md");
  if (fs.existsSync(takesPath)) takes = parseTakesPacked(fs.readFileSync(takesPath, "utf8"));

  const renders = ["final.mp4", "final_no_subs.mp4", "preview.mp4", "base.mp4", "base_preview.mp4", "base_draft.mp4"]
    .map((name) => {
      const p = path.join(ed, name);
      if (!fs.existsSync(p)) return null;
      const st = fs.statSync(p);
      return { name, rel: `edit/${name}`, size: st.size, mtimeMs: st.mtimeMs };
    })
    .filter((x): x is NonNullable<typeof x> => !!x)
    .sort((a, b) => b.mtimeMs - a.mtimeMs);

  const verifyDir = path.join(ed, "verify");
  const verifyImages = fs.existsSync(verifyDir)
    ? fs
        .readdirSync(verifyDir)
        .filter((f) => f.endsWith(".png") || f.endsWith(".jpg"))
        .sort()
        .map((f) => `edit/verify/${f}`)
    : [];

  const animDir = path.join(ed, "animations");
  const animations: AnimationSlot[] = [];
  if (fs.existsSync(animDir)) {
    for (const slot of fs.readdirSync(animDir).sort()) {
      const sd = path.join(animDir, slot);
      if (!fs.statSync(sd).isDirectory()) continue;
      const files = fs.readdirSync(sd);
      const render =
        files.find((f) => f === "render.mp4") ?? files.find((f) => f === "render.webm") ?? null;
      const briefFile = files.find((f) => f.toLowerCase().endsWith(".md"));
      animations.push({
        id: slot,
        dir: `edit/animations/${slot}`,
        render: render ? `edit/animations/${slot}/${render}` : null,
        files,
        brief: briefFile ? fs.readFileSync(path.join(sd, briefFile), "utf8").slice(0, 4000) : null,
      });
    }
  }

  const pmPath = path.join(ed, "project.md");
  const projectMd = fs.existsSync(pmPath) ? fs.readFileSync(pmPath, "utf8") : null;

  const trDir = path.join(ed, "transcripts");
  const transcribedSources = fs.existsSync(trDir)
    ? fs.readdirSync(trDir).filter((f) => f.endsWith(".json")).map((f) => path.parse(f).name).sort()
    : [];

  const subtitleFiles = ["master.srt", "master.ass"]
    .filter((f) => fs.existsSync(path.join(ed, f)))
    .map((f) => `edit/${f}`);

  let subStyle: SubtitleStyle | null = null;
  const subCfgPath = path.join(ed, "studio_subs.json");
  if (fs.existsSync(subCfgPath)) {
    try {
      subStyle = { ...DEFAULT_SUB_STYLE, ...JSON.parse(fs.readFileSync(subCfgPath, "utf8")) };
    } catch {}
  }

  const fontsDir = path.join(ed, "fonts");
  const fonts = fs.existsSync(fontsDir)
    ? fs.readdirSync(fontsDir).filter((f) => /\.(ttf|otf)$/i.test(f)).map((f) => `edit/fonts/${f}`)
    : [];

  const probes = await loadProbes(dir, resolvedSources);

  return {
    dir,
    name: path.basename(dir),
    hasEdit,
    edl,
    edlMtimeMs,
    sourceFiles,
    resolvedSources,
    missingSources,
    takes,
    probes,
    renders,
    verifyImages,
    animations,
    projectMd,
    sessions: projectMd ? parseSessions(projectMd) : [],
    transcribedSources,
    subtitleFiles,
    subStyle,
    fonts,
    gradePresets: await gradePresets(),
  };
}

// ---------- EDL save with history ----------

export function saveEdl(dir: string, edl: Edl): void {
  const ed = editDir(dir);
  fs.mkdirSync(ed, { recursive: true });
  const edlPath = path.join(ed, "edl.json");
  const histDir = path.join(cacheDir(dir), "edl_history");
  fs.mkdirSync(histDir, { recursive: true });
  if (fs.existsSync(edlPath)) {
    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    fs.copyFileSync(edlPath, path.join(histDir, `edl-${ts}.json`));
    // keep last 50
    const all = fs.readdirSync(histDir).sort();
    for (const f of all.slice(0, Math.max(0, all.length - 50))) {
      fs.unlinkSync(path.join(histDir, f));
    }
  }
  fs.writeFileSync(edlPath, JSON.stringify(edl, null, 2));
}

export function edlHistory(dir: string): string[] {
  const histDir = path.join(cacheDir(dir), "edl_history");
  if (!fs.existsSync(histDir)) return [];
  return fs.readdirSync(histDir).sort().reverse();
}

export function restoreEdl(dir: string, name: string): Edl {
  const histDir = path.join(cacheDir(dir), "edl_history");
  const p = path.join(histDir, path.basename(name));
  const edl = JSON.parse(fs.readFileSync(p, "utf8"));
  saveEdl(dir, edl);
  return edl;
}
