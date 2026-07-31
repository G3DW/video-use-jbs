"use client";

import type { AgentEvent, Edl, JobInfo, ProjectState, SubtitleStyle, WordEntry } from "../types";

export function mediaUrl(dir: string, rel: string) {
  return `/api/media?dir=${encodeURIComponent(dir)}&path=${encodeURIComponent(rel)}`;
}

export function frameUrl(dir: string, rel: string, t: number, w = 320, vf?: string, preset?: string) {
  let u = `/api/frame?dir=${encodeURIComponent(dir)}&path=${encodeURIComponent(rel)}&t=${t.toFixed(2)}&w=${w}`;
  if (vf) u += `&vf=${encodeURIComponent(vf)}`;
  if (preset) u += `&preset=${encodeURIComponent(preset)}`;
  return u;
}

export async function fetchProject(dir: string): Promise<ProjectState> {
  const r = await fetch(`/api/project?dir=${encodeURIComponent(dir)}`, { cache: "no-store" });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error ?? "failed to load project");
  return j;
}

export async function saveEdl(dir: string, edl: Edl): Promise<void> {
  const r = await fetch("/api/edl", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dir, edl }),
  });
  const j = await r.json();
  if (!j.ok) throw new Error(j.error ?? "failed to save EDL");
}

export async function fetchEdlHistory(dir: string): Promise<string[]> {
  const r = await fetch(`/api/edl?dir=${encodeURIComponent(dir)}`, { cache: "no-store" });
  return (await r.json()).history ?? [];
}

export async function restoreEdl(dir: string, name: string): Promise<void> {
  const r = await fetch("/api/edl", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dir, restore: name }),
  });
  const j = await r.json();
  if (!j.ok) throw new Error(j.error ?? "failed to restore EDL");
}

export async function fetchWords(dir: string, source: string): Promise<WordEntry[]> {
  const r = await fetch(
    `/api/words?dir=${encodeURIComponent(dir)}&source=${encodeURIComponent(source)}`,
    { cache: "no-store" }
  );
  return (await r.json()).words ?? [];
}

export async function startJob(
  dir: string,
  kind: string,
  extra: Record<string, unknown> = {}
): Promise<{ job?: JobInfo; output?: string; ok?: boolean; cueCount?: number; error?: string }> {
  const r = await fetch("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dir, kind, ...extra }),
  });
  return r.json();
}

export async function buildSubs(dir: string, style: SubtitleStyle) {
  return startJob(dir, "build_subs", { style });
}

export async function listJobs(): Promise<JobInfo[]> {
  const r = await fetch("/api/jobs", { cache: "no-store" });
  return (await r.json()).jobs ?? [];
}

export function subscribeJob(id: string, onUpdate: (j: JobInfo) => void): () => void {
  const es = new EventSource(`/api/jobs/${id}/events`);
  es.onmessage = (e) => {
    try {
      const j = JSON.parse(e.data) as JobInfo;
      onUpdate(j);
      if (j.status !== "running") es.close();
    } catch {}
  };
  es.onerror = () => es.close();
  return () => es.close();
}

export async function agentSend(dir: string, text: string) {
  const r = await fetch("/api/agent", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dir, text }),
  });
  const j = await r.json();
  if (!j.ok) throw new Error(j.error ?? "agent error");
}

export async function agentAction(dir: string, action: "interrupt" | "reset") {
  await fetch("/api/agent", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dir, action }),
  });
}

export async function agentGet(dir: string): Promise<{ running: boolean; events: AgentEvent[] }> {
  const r = await fetch(`/api/agent?dir=${encodeURIComponent(dir)}`, { cache: "no-store" });
  return r.json();
}

export function subscribeAgent(dir: string, onEvent: (e: AgentEvent) => void): () => void {
  const es = new EventSource(`/api/agent/events?dir=${encodeURIComponent(dir)}`);
  es.onmessage = (e) => {
    try {
      onEvent(JSON.parse(e.data));
    } catch {}
  };
  return () => es.close();
}
