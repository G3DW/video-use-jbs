import { spawn } from "child_process";
import { EventEmitter } from "events";
import crypto from "crypto";
import type { JobInfo, JobKind } from "../types";

interface JobRecord extends JobInfo {
  emitter: EventEmitter;
  kill?: () => void;
}

// Survive Next.js dev-server module reloads.
const g = globalThis as unknown as { __studioJobs?: Map<string, JobRecord> };
const jobs: Map<string, JobRecord> = (g.__studioJobs ??= new Map());

function publish(job: JobRecord) {
  job.emitter.emit("update", toInfo(job));
}

function toInfo(j: JobRecord): JobInfo {
  const { emitter: _e, kill: _k, ...info } = j;
  return { ...info, lines: info.lines.slice(-400) };
}

/** Parse helper stdout lines into coarse progress. */
function parseProgress(job: JobRecord, line: string) {
  if (job.kind.startsWith("render")) {
    let m = line.match(/^extracting (\d+) segment/);
    if (m) {
      // extraction ≈ 80% of the work, then concat/composite/loudnorm
      job.progress = { done: 0, total: parseInt(m[1], 10) + 3 };
      return;
    }
    m = line.match(/^\s+\[(\d+)\]\s/);
    if (m && job.progress) {
      job.progress.done = Math.min(parseInt(m[1], 10) + 1, job.progress.total);
      return;
    }
    if (/^concat →/.test(line) && job.progress) job.progress.done += 1;
    if (/^compositing →/.test(line) && job.progress) job.progress.done += 1;
    if (/^loudness normalization/.test(line) && job.progress) job.progress.done += 1;
    const done = line.match(/^done: (.+?) \(/);
    if (done) {
      if (job.progress) job.progress.done = job.progress.total;
      job.outputs.push(done[1]);
    }
  } else if (job.kind === "transcribe") {
    const m = line.match(/(\d+)\s*\/\s*(\d+)/);
    if (m) job.progress = { done: parseInt(m[1], 10), total: parseInt(m[2], 10) };
  } else if (job.kind === "timeline_view") {
    const m = line.match(/^saved: (\S+)/);
    if (m) job.outputs.push(m[1]);
  }
}

export function startJob(opts: {
  kind: JobKind;
  label: string;
  cmd: string;
  args: string[];
  cwd: string;
  env?: NodeJS.ProcessEnv;
}): JobInfo {
  const id = crypto.randomBytes(6).toString("hex");
  const job: JobRecord = {
    id,
    kind: opts.kind,
    label: opts.label,
    status: "running",
    lines: [],
    progress: null,
    startedAt: Date.now(),
    endedAt: null,
    outputs: [],
    emitter: new EventEmitter(),
  };
  job.emitter.setMaxListeners(50);
  jobs.set(id, job);

  const child = spawn(opts.cmd, opts.args, {
    cwd: opts.cwd,
    env: opts.env ?? process.env,
  });
  job.kill = () => child.kill("SIGTERM");

  let buf = "";
  const onData = (chunk: Buffer) => {
    buf += chunk.toString();
    let idx: number;
    while ((idx = buf.indexOf("\n")) !== -1) {
      const line = buf.slice(0, idx).trimEnd();
      buf = buf.slice(idx + 1);
      if (!line) continue;
      job.lines.push(line);
      if (job.lines.length > 2000) job.lines.splice(0, 1000);
      parseProgress(job, line);
      publish(job);
    }
  };
  child.stdout.on("data", onData);
  child.stderr.on("data", onData);
  child.on("error", (err) => {
    job.status = "error";
    job.error = String(err);
    job.endedAt = Date.now();
    publish(job);
  });
  child.on("close", (code) => {
    if (job.status !== "error") {
      job.status = code === 0 ? "done" : "error";
      if (code !== 0) job.error = `exit code ${code}`;
    }
    job.endedAt = Date.now();
    publish(job);
  });

  // prune finished jobs older than 2h
  for (const [jid, j] of jobs) {
    if (j.endedAt && Date.now() - j.endedAt > 2 * 3600_000) jobs.delete(jid);
  }

  return toInfo(job);
}

export function getJob(id: string): JobInfo | null {
  const j = jobs.get(id);
  return j ? toInfo(j) : null;
}

export function listJobs(): JobInfo[] {
  return [...jobs.values()].map(toInfo).sort((a, b) => b.startedAt - a.startedAt);
}

export function killJob(id: string): boolean {
  const j = jobs.get(id);
  if (j?.kill && j.status === "running") {
    j.kill();
    return true;
  }
  return false;
}

export function subscribeJob(id: string, fn: (info: JobInfo) => void): (() => void) | null {
  const j = jobs.get(id);
  if (!j) return null;
  j.emitter.on("update", fn);
  return () => j.emitter.off("update", fn);
}
