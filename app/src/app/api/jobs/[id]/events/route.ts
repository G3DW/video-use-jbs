import { NextRequest } from "next/server";
import { getJob, subscribeJob } from "@/lib/server/jobs";
import type { JobInfo } from "@/lib/types";

export const dynamic = "force-dynamic";

/** SSE stream of one job's updates. Sends current state immediately, then deltas. */
export async function GET(_req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const initial = getJob(id);
  if (!initial) return new Response("no such job", { status: 404 });

  const encoder = new TextEncoder();
  let cleanup: (() => void) | null = null;

  const stream = new ReadableStream({
    start(controller) {
      const send = (info: JobInfo) => {
        try {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(info)}\n\n`));
          if (info.status !== "running") {
            cleanup?.();
            controller.close();
          }
        } catch {}
      };
      send(initial);
      if (initial.status === "running") {
        cleanup = subscribeJob(id, send);
      }
    },
    cancel() {
      cleanup?.();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-store",
      Connection: "keep-alive",
    },
  });
}
