// Shared types between server and client.

export interface EdlRange {
  source: string;
  start: number;
  end: number;
  beat?: string;
  quote?: string;
  reason?: string;
  note?: string;
}

export interface EdlOverlay {
  file: string;
  start_in_output: number;
  duration: number;
}

export interface Edl {
  version: number;
  sources: Record<string, string>;
  ranges: EdlRange[];
  grade?: string | null;
  overlays?: EdlOverlay[];
  subtitles?: string | null;
  total_duration_s?: number;
}

export interface Phrase {
  start: number;
  end: number;
  speaker: string;
  text: string;
}

export interface Take {
  source: string;
  duration: number;
  phrases: Phrase[];
}

export interface SourceProbe {
  duration: number;
  width: number;
  height: number;
  fps: number;
  vcodec: string;
  hdr: boolean;
  playable: boolean; // h264/vp9/av1 → browser can play directly
}

export interface RenderInfo {
  name: string;
  rel: string;
  size: number;
  mtimeMs: number;
}

export interface AnimationSlot {
  id: string;
  dir: string;
  render: string | null; // rel path to render.mp4/webm
  files: string[];
  brief: string | null;
}

export interface ProjectSession {
  title: string;
  body: string;
}

export interface SubtitleStyle {
  enabled: boolean;
  fontFamily: string;
  fontFile: string | null;
  sizePct: number; // font size as % of frame height
  bold: boolean;
  uppercase: boolean;
  chunkMode: "two-word" | "natural";
  marginVPct: number; // caption baseline distance from bottom, % of height
  maxWidthPct: number;
  backdrop: "box" | "outline";
  primaryColor: string; // hex
  outlineColor: string; // hex
  boxOpacity: number; // 0..1 (box mode)
}

export interface ProjectState {
  dir: string;
  name: string;
  hasEdit: boolean;
  edl: Edl | null;
  edlMtimeMs: number | null;
  sourceFiles: string[]; // video files at project root
  resolvedSources: Record<string, string>; // source name → rel path that exists
  missingSources: string[];
  takes: Take[];
  probes: Record<string, SourceProbe>;
  renders: RenderInfo[];
  verifyImages: string[];
  animations: AnimationSlot[];
  projectMd: string | null;
  sessions: ProjectSession[];
  transcribedSources: string[];
  subtitleFiles: string[]; // master.srt / master.ass rel paths
  subStyle: SubtitleStyle | null;
  fonts: string[];
  gradePresets: string[];
}

export type JobKind =
  | "render_final"
  | "render_preview"
  | "render_draft"
  | "transcribe"
  | "pack"
  | "timeline_view"
  | "build_subs"
  | "probe";

export interface JobInfo {
  id: string;
  kind: JobKind;
  label: string;
  status: "running" | "done" | "error";
  lines: string[];
  progress: { done: number; total: number } | null;
  startedAt: number;
  endedAt: number | null;
  outputs: string[]; // rel paths produced
  error?: string;
}

// Agent event stream payloads
export type AgentEvent =
  | { type: "status"; running: boolean; sessionId: string | null }
  | { type: "user_text"; text: string; ts: number }
  | { type: "assistant_text"; text: string; ts: number }
  | { type: "tool_use"; name: string; summary: string; ts: number }
  | { type: "tool_result"; name: string; summary: string; isError: boolean; ts: number }
  | { type: "strategy"; text: string; ts: number }
  | { type: "result"; subtype: string; costUsd: number | null; ts: number }
  | { type: "error"; message: string; ts: number };

export interface WordEntry {
  t: string; // text
  s: number; // start
  e: number; // end
}
