import { NextRequest, NextResponse } from "next/server";
import { checkProjectDir, rememberProject } from "@/lib/server/paths";
import { loadProject } from "@/lib/server/project";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  try {
    const dir = checkProjectDir(req.nextUrl.searchParams.get("dir") ?? "");
    rememberProject(dir);
    const state = await loadProject(dir);
    return NextResponse.json(state);
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 400 });
  }
}
