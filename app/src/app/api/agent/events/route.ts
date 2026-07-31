import { NextRequest } from "next/server";
import { checkProjectDir } from "@/lib/server/paths";
import { subscribeAgent } from "@/lib/server/agent";
import type { AgentEvent } from "@/lib/types";

export const dynamic = "force-dynamic";

/** SSE stream of agent events for one project. */
export async function GET(req: NextRequest) {
  let dir: string;
  try {
    dir = checkProjectDir(req.nextUrl.searchParams.get("dir") ?? "");
  } catch (err) {
    return new Response(String(err), { status: 400 });
  }

  const encoder = new TextEncoder();
  let cleanup: (() => void) | null = null;
  let ping: ReturnType<typeof setInterval> | null = null;

  const stream = new ReadableStream({
    start(controller) {
      const send = (ev: AgentEvent) => {
        try {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(ev)}\n\n`));
        } catch {}
      };
      cleanup = subscribeAgent(dir, send);
      ping = setInterval(() => {
        try {
          controller.enqueue(encoder.encode(`: ping\n\n`));
        } catch {}
      }, 15000);
    },
    cancel() {
      cleanup?.();
      if (ping) clearInterval(ping);
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
