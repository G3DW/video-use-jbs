import fs from "fs";
import path from "path";

// The app lives at <repo>/app — the video-use repo root is one level up.
// Override with VIDEO_USE_ROOT if the app runs from elsewhere.
export const REPO_ROOT = process.env.VIDEO_USE_ROOT
  ? path.resolve(process.env.VIDEO_USE_ROOT)
  : path.resolve(process.cwd(), "..");
export const HELPERS_DIR = path.join(REPO_ROOT, "helpers");
export const SKILL_MD = path.join(REPO_ROOT, "SKILL.md");

const CONFIG_PATH = path.join(process.cwd(), ".studio.json");

export interface StudioConfig {
  recentProjects: string[];
}

export function readConfig(): StudioConfig {
  try {
    return JSON.parse(fs.readFileSync(CONFIG_PATH, "utf8"));
  } catch {
    return { recentProjects: [] };
  }
}

export function writeConfig(cfg: StudioConfig) {
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(cfg, null, 2));
}

export function rememberProject(dir: string) {
  const cfg = readConfig();
  cfg.recentProjects = [dir, ...cfg.recentProjects.filter((d) => d !== dir)].slice(0, 10);
  writeConfig(cfg);
}

export function pythonBin(): string {
  if (process.env.PYTHON_BIN) return process.env.PYTHON_BIN;
  for (const cand of [
    path.join(REPO_ROOT, ".venv", "bin", "python"),
    path.join(REPO_ROOT, ".venv", "Scripts", "python.exe"),
  ]) {
    if (fs.existsSync(cand)) return cand;
  }
  return "python3";
}

/** PATH with optional FFMPEG_DIR prepended (Joe's machine needs ffmpeg-full for libass). */
export function jobEnv(): NodeJS.ProcessEnv {
  const env = { ...process.env };
  if (process.env.FFMPEG_DIR) {
    env.PATH = `${process.env.FFMPEG_DIR}${path.delimiter}${env.PATH ?? ""}`;
  }
  return env;
}

/** Resolve a client-supplied relative path inside a project dir. Throws on escape. */
export function safeJoin(projectDir: string, rel: string): string {
  const abs = path.resolve(projectDir, rel);
  const root = path.resolve(projectDir);
  if (abs !== root && !abs.startsWith(root + path.sep)) {
    throw new Error(`path escapes project dir: ${rel}`);
  }
  return abs;
}

/** Validate a project dir the client asked to open. Must exist and be a directory. */
export function checkProjectDir(dir: string): string {
  const abs = path.resolve(dir);
  const st = fs.statSync(abs); // throws if missing
  if (!st.isDirectory()) throw new Error(`not a directory: ${abs}`);
  return abs;
}

export const VIDEO_EXTS = new Set([".mov", ".mp4", ".m4v", ".mkv", ".webm", ".avi", ".mts"]);
