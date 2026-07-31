import fs from "fs";
import path from "path";
import { EventEmitter } from "events";
import { SKILL_MD } from "./paths";
import { cacheDir } from "./project";
import type { AgentEvent } from "../types";

// The Claude Agent SDK drives the same loop Claude Code runs in the terminal —
// same skill rules, same helpers — but streamed into the UI.

interface AgentSession {
  dir: string;
  sessionId: string | null;
  running: boolean;
  events: AgentEvent[];
  emitter: EventEmitter;
  interrupt: (() => Promise<void>) | null;
}

const g = globalThis as unknown as { __studioAgents?: Map<string, AgentSession> };
const sessions: Map<string, AgentSession> = (g.__studioAgents ??= new Map());

function logPath(dir: string) {
  return path.join(cacheDir(dir), "agent_log.json");
}

function getSession(dir: string): AgentSession {
  let s = sessions.get(dir);
  if (!s) {
    s = { dir, sessionId: null, running: false, events: [], emitter: new EventEmitter(), interrupt: null };
    s.emitter.setMaxListeners(50);
    try {
      const saved = JSON.parse(fs.readFileSync(logPath(dir), "utf8"));
      s.events = saved.events ?? [];
      s.sessionId = saved.sessionId ?? null;
    } catch {}
    sessions.set(dir, s);
  }
  return s;
}

function persist(s: AgentSession) {
  try {
    fs.mkdirSync(cacheDir(s.dir), { recursive: true });
    fs.writeFileSync(
      logPath(s.dir),
      JSON.stringify({ sessionId: s.sessionId, events: s.events.slice(-500) })
    );
  } catch {}
}

function push(s: AgentSession, ev: AgentEvent) {
  s.events.push(ev);
  if (s.events.length > 1000) s.events.splice(0, 400);
  s.emitter.emit("event", ev);
  persist(s);
}

function summarizeInput(name: string, input: unknown): string {
  try {
    const j = input as Record<string, unknown>;
    if (name === "Bash") return String(j.command ?? "").slice(0, 200);
    if (name === "Read") return String(j.file_path ?? "");
    if (name === "Write" || name === "Edit") return String(j.file_path ?? "");
    if (name === "Agent" || name === "Task") return String(j.description ?? "").slice(0, 120);
    const str = JSON.stringify(j);
    return str.length > 200 ? str.slice(0, 200) + "…" : str;
  } catch {
    return "";
  }
}

const STUDIO_APPEND = `
## Studio UI bridge (this session runs inside the video-use studio web app)

- The user sees your messages in a chat panel, your tool calls as a live step console, and edl.json / renders / verify images in dedicated panels that auto-refresh from disk. Keep prose answers short; the artifacts speak for themselves.
- When you propose an editing strategy and need confirmation (Hard Rule 11), wrap the plain-English strategy paragraph in <studio:strategy> ... </studio:strategy> tags. The UI renders it as a confirmation card with Approve / Revise buttons. Wait for the user's reply as usual.
- The UI edits edl.json directly (accept/reject cuts, drag boundaries, grade + subtitle settings). Re-read edl.json from disk before every render or modification — never assume your last write is current.
- Subtitle styling may be managed by the studio in edit/studio_subs.json + edit/master.ass (full .ass, not force_style). If present, respect it.
- All outputs still follow the skill's directory layout under edit/.
`;

export async function sendMessage(dir: string, text: string): Promise<void> {
  const s = getSession(dir);
  if (s.running) throw new Error("agent is already running — wait or interrupt first");
  s.running = true;
  push(s, { type: "user_text", text, ts: Date.now() });
  push(s, { type: "status", running: true, sessionId: s.sessionId });

  let skill = "";
  try {
    skill = fs.readFileSync(SKILL_MD, "utf8");
  } catch {}

  (async () => {
    try {
      const { query } = await import("@anthropic-ai/claude-agent-sdk");
      const q = query({
        prompt: text,
        options: {
          cwd: dir,
          ...(s.sessionId ? { resume: s.sessionId } : {}),
          permissionMode: "bypassPermissions",
          systemPrompt: {
            type: "preset",
            preset: "claude_code",
            append: `${skill}\n${STUDIO_APPEND}`,
          },
          stderr: () => {},
        },
      });
      s.interrupt = () => q.interrupt();

      for await (const msg of q) {
        if (msg.type === "system" && msg.subtype === "init") {
          s.sessionId = msg.session_id;
        } else if (msg.type === "assistant") {
          for (const block of msg.message.content ?? []) {
            if (block.type === "text" && block.text.trim()) {
              const m = block.text.match(/<studio:strategy>([\s\S]*?)<\/studio:strategy>/);
              if (m) {
                const rest = block.text.replace(m[0], "").trim();
                if (rest) push(s, { type: "assistant_text", text: rest, ts: Date.now() });
                push(s, { type: "strategy", text: m[1].trim(), ts: Date.now() });
              } else {
                push(s, { type: "assistant_text", text: block.text, ts: Date.now() });
              }
            } else if (block.type === "tool_use") {
              push(s, {
                type: "tool_use",
                name: block.name,
                summary: summarizeInput(block.name, block.input),
                ts: Date.now(),
              });
            }
          }
        } else if (msg.type === "user") {
          const content = (msg as { message?: { content?: unknown } }).message?.content;
          if (Array.isArray(content)) {
            for (const block of content) {
              if (block?.type === "tool_result") {
                let summary = "";
                if (typeof block.content === "string") summary = block.content;
                else if (Array.isArray(block.content))
                  summary = block.content
                    .map((c: { type?: string; text?: string }) => (c.type === "text" ? c.text : `[${c.type}]`))
                    .join(" ");
                summary = (summary ?? "").slice(0, 220);
                push(s, {
                  type: "tool_result",
                  name: "",
                  summary,
                  isError: !!block.is_error,
                  ts: Date.now(),
                });
              }
            }
          }
        } else if (msg.type === "result") {
          push(s, {
            type: "result",
            subtype: msg.subtype,
            costUsd: "total_cost_usd" in msg ? msg.total_cost_usd : null,
            ts: Date.now(),
          });
        }
      }
    } catch (err) {
      push(s, { type: "error", message: String(err), ts: Date.now() });
    } finally {
      s.running = false;
      s.interrupt = null;
      push(s, { type: "status", running: false, sessionId: s.sessionId });
    }
  })();
}

export async function interruptAgent(dir: string): Promise<boolean> {
  const s = getSession(dir);
  if (s.interrupt) {
    try {
      await s.interrupt();
    } catch {}
    return true;
  }
  return false;
}

export function resetAgent(dir: string) {
  const s = getSession(dir);
  s.sessionId = null;
  s.events = [];
  persist(s);
  s.emitter.emit("event", { type: "status", running: s.running, sessionId: null });
}

export function agentState(dir: string): { running: boolean; sessionId: string | null; events: AgentEvent[] } {
  const s = getSession(dir);
  return { running: s.running, sessionId: s.sessionId, events: s.events.slice(-500) };
}

export function subscribeAgent(dir: string, fn: (ev: AgentEvent) => void): () => void {
  const s = getSession(dir);
  s.emitter.on("event", fn);
  return () => s.emitter.off("event", fn);
}
