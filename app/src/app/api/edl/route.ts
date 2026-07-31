import { NextRequest, NextResponse } from "next/server";
import { checkProjectDir } from "@/lib/server/paths";
import { edlHistory, restoreEdl, saveEdl } from "@/lib/server/project";
import type { Edl } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  try {
    const dir = checkProjectDir(req.nextUrl.searchParams.get("dir") ?? "");
    return NextResponse.json({ history: edlHistory(dir) });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 400 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const dir = checkProjectDir(body.dir);
    if (body.restore) {
      const edl = restoreEdl(dir, body.restore);
      return NextResponse.json({ ok: true, edl });
    }
    const edl = body.edl as Edl;
    if (!edl || !Array.isArray(edl.ranges)) throw new Error("invalid EDL");
    // sanity: every range end > start, sources known
    for (const r of edl.ranges) {
      if (!(r.end > r.start)) throw new Error(`range end <= start for ${r.source}`);
      if (!edl.sources[r.source]) throw new Error(`unknown source ${r.source}`);
    }
    saveEdl(dir, edl);
    return NextResponse.json({ ok: true });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 400 });
  }
}
