import { NextRequest, NextResponse } from "next/server";
import { checkProjectDir } from "@/lib/server/paths";
import { loadWords } from "@/lib/server/project";

export const dynamic = "force-dynamic";

/** Word-level timestamps for one source (for word-boundary snapping in the timeline). */
export async function GET(req: NextRequest) {
  try {
    const dir = checkProjectDir(req.nextUrl.searchParams.get("dir") ?? "");
    const source = (req.nextUrl.searchParams.get("source") ?? "").replace(/[^\w.-]/g, "");
    return NextResponse.json({ words: loadWords(dir, source) });
  } catch (err) {
    return NextResponse.json({ error: String(err), words: [] }, { status: 200 });
  }
}
