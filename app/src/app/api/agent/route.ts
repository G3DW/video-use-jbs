import { NextRequest, NextResponse } from "next/server";
import { checkProjectDir } from "@/lib/server/paths";
import { agentState, interruptAgent, resetAgent, sendMessage } from "@/lib/server/agent";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  try {
    const dir = checkProjectDir(req.nextUrl.searchParams.get("dir") ?? "");
    return NextResponse.json(agentState(dir));
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 400 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const dir = checkProjectDir(body.dir);
    if (body.action === "interrupt") {
      return NextResponse.json({ ok: await interruptAgent(dir) });
    }
    if (body.action === "reset") {
      resetAgent(dir);
      return NextResponse.json({ ok: true });
    }
    await sendMessage(dir, String(body.text ?? "").trim());
    return NextResponse.json({ ok: true });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 400 });
  }
}
