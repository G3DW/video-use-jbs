"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { AgentEvent, Edl, JobInfo, ProjectState, WordEntry } from "@/lib/types";
import {
  agentAction,
  agentGet,
  agentSend,
  fetchProject,
  fetchWords,
  listJobs,
  saveEdl,
  startJob,
  subscribeAgent,
  subscribeJob,
} from "@/lib/client/api";

export interface Studio {
  dir: string;
  proj: ProjectState | null;
  loadError: string | null;
  refresh: () => Promise<void>;

  // EDL editing
  updateEdl: (fn: (edl: Edl) => Edl, opts?: { save?: boolean }) => Promise<void>;
  draftEdl: Edl | null; // during drags — takes precedence for display
  setDraftEdl: (e: Edl | null) => void;
  commitDraft: () => Promise<void>;

  // selection + playback
  selection: number | null;
  setSelection: (i: number | null) => void;
  playhead: number;
  setPlayhead: (t: number) => void;
  seekReq: { t: number; nonce: number } | null;
  seek: (t: number) => void;
  playerRel: string | null; // which render file is loaded
  setPlayerRel: (rel: string | null) => void;

  // words
  getWords: (source: string) => Promise<WordEntry[]>;
  wordsCache: Map<string, WordEntry[]>;

  // jobs
  jobs: JobInfo[];
  runJob: (kind: string, extra?: Record<string, unknown>) => Promise<JobInfo | null>;
  killJob: (id: string) => Promise<void>;

  // agent
  agentEvents: AgentEvent[];
  agentRunning: boolean;
  sendAgent: (text: string) => Promise<void>;
  interruptAgent: () => Promise<void>;
  resetAgent: () => Promise<void>;
}

const Ctx = createContext<Studio | null>(null);

export function useStudio(): Studio {
  const s = useContext(Ctx);
  if (!s) throw new Error("useStudio outside provider");
  return s;
}

export function StudioProvider({ dir, children }: { dir: string; children: React.ReactNode }) {
  const [proj, setProj] = useState<ProjectState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [draftEdl, setDraftEdl] = useState<Edl | null>(null);
  const [selection, setSelection] = useState<number | null>(null);
  const [playhead, setPlayhead] = useState(0);
  const [seekReq, setSeekReq] = useState<{ t: number; nonce: number } | null>(null);
  const [playerRel, setPlayerRel] = useState<string | null>(null);
  const [jobs, setJobs] = useState<JobInfo[]>([]);
  const [agentEvents, setAgentEvents] = useState<AgentEvent[]>([]);
  const [agentRunning, setAgentRunning] = useState(false);
  const wordsCache = useRef(new Map<string, WordEntry[]>()).current;

  const refresh = useCallback(async () => {
    try {
      const p = await fetchProject(dir);
      setProj(p);
      setLoadError(null);
    } catch (err) {
      setLoadError(String(err));
    }
  }, [dir]);

  useEffect(() => {
    refresh();
    listJobs().then(setJobs).catch(() => {});
    agentGet(dir)
      .then((s) => {
        setAgentEvents(s.events ?? []);
        setAgentRunning(!!s.running);
      })
      .catch(() => {});
    const off = subscribeAgent(dir, (ev) => {
      if (ev.type === "status") setAgentRunning(ev.running);
      else setAgentEvents((prev) => [...prev.slice(-800), ev]);
      // agent touches files constantly — refresh on tool results & completion
      if (ev.type === "result" || ev.type === "tool_result") refresh();
    });
    return off;
  }, [dir, refresh]);

  // refresh on window focus (files change outside the app too)
  useEffect(() => {
    const onFocus = () => refresh();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [refresh]);

  const updateEdl = useCallback(
    async (fn: (edl: Edl) => Edl, opts?: { save?: boolean }) => {
      if (!proj?.edl) return;
      const next = fn(structuredClone(proj.edl));
      setProj({ ...proj, edl: next });
      if (opts?.save !== false) {
        try {
          await saveEdl(dir, next);
        } catch (err) {
          alert(String(err));
        }
        refresh();
      }
    },
    [dir, proj, refresh]
  );

  const commitDraft = useCallback(async () => {
    if (!draftEdl) return;
    setProj((p) => (p ? { ...p, edl: draftEdl } : p));
    setDraftEdl(null);
    try {
      await saveEdl(dir, draftEdl);
    } catch (err) {
      alert(String(err));
    }
    refresh();
  }, [dir, draftEdl, refresh]);

  const seek = useCallback((t: number) => {
    setSeekReq({ t, nonce: Date.now() });
    setPlayhead(t);
  }, []);

  const getWords = useCallback(
    async (source: string) => {
      const hit = wordsCache.get(source);
      if (hit) return hit;
      const w = await fetchWords(dir, source);
      wordsCache.set(source, w);
      return w;
    },
    [dir, wordsCache]
  );

  const trackJob = useCallback(
    (job: JobInfo) => {
      setJobs((prev) => [job, ...prev.filter((j) => j.id !== job.id)]);
      subscribeJob(job.id, (j) => {
        setJobs((prev) => prev.map((x) => (x.id === j.id ? j : x)));
        if (j.status !== "running") refresh();
      });
    },
    [refresh]
  );

  const runJob = useCallback(
    async (kind: string, extra: Record<string, unknown> = {}) => {
      const res = await startJob(dir, kind, extra);
      if (res.error) {
        alert(res.error);
        return null;
      }
      if (res.job) {
        trackJob(res.job);
        return res.job;
      }
      refresh();
      return null;
    },
    [dir, refresh, trackJob]
  );

  const killJobFn = useCallback(
    async (id: string) => {
      await startJob(dir, "kill", { kill: id });
      listJobs().then(setJobs).catch(() => {});
    },
    [dir]
  );

  const sendAgent = useCallback(
    async (text: string) => {
      await agentSend(dir, text);
    },
    [dir]
  );

  const value = useMemo<Studio>(
    () => ({
      dir,
      proj,
      loadError,
      refresh,
      updateEdl,
      draftEdl,
      setDraftEdl,
      commitDraft,
      selection,
      setSelection,
      playhead,
      setPlayhead,
      seekReq,
      seek,
      playerRel,
      setPlayerRel,
      getWords,
      wordsCache,
      jobs,
      runJob,
      killJob: killJobFn,
      agentEvents,
      agentRunning,
      sendAgent,
      interruptAgent: () => agentAction(dir, "interrupt"),
      resetAgent: async () => {
        await agentAction(dir, "reset");
        setAgentEvents([]);
      },
    }),
    [
      dir, proj, loadError, refresh, updateEdl, draftEdl, commitDraft, selection,
      playhead, seekReq, seek, playerRel, getWords, wordsCache, jobs, runJob,
      killJobFn, agentEvents, agentRunning, sendAgent,
    ]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
