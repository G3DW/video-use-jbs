import { execFile } from "child_process";
import { promisify } from "util";
import fs from "fs";
import path from "path";
import crypto from "crypto";
import { jobEnv } from "./paths";
import type { SourceProbe } from "../types";

const pexec = promisify(execFile);

const HDR_TRANSFERS = new Set(["smpte2084", "arib-std-b67"]);
const BROWSER_CODECS = new Set(["h264", "vp8", "vp9", "av1"]);

export async function probeVideo(file: string): Promise<SourceProbe> {
  const { stdout } = await pexec(
    "ffprobe",
    // full -show_streams so side_data_list (rotation) is present on every ffprobe version
    ["-v", "error", "-select_streams", "v:0", "-show_streams", "-show_format", "-of", "json", file],
    { env: jobEnv() }
  );
  const j = JSON.parse(stdout);
  const s = j.streams?.[0] ?? {};
  const [num, den] = String(s.avg_frame_rate ?? "0/1").split("/").map(Number);
  // iPhone footage often stores rotation as display-matrix side data:
  // ffprobe's width/height are pre-rotation, so swap for 90/270.
  let w = s.width ?? 0;
  let h = s.height ?? 0;
  let rot = (s.side_data_list ?? []).find(
    (d: { rotation?: number }) => typeof d.rotation === "number"
  )?.rotation;
  if (rot == null && s.tags?.rotate != null) rot = parseFloat(s.tags.rotate);
  if (rot != null && Math.abs(Math.round(rot)) % 180 === 90) [w, h] = [h, w];
  return {
    duration: parseFloat(j.format?.duration ?? "0"),
    width: w,
    height: h,
    fps: den ? Math.round((num / den) * 100) / 100 : 0,
    vcodec: s.codec_name ?? "unknown",
    hdr: HDR_TRANSFERS.has(s.color_transfer ?? ""),
    playable: BROWSER_CODECS.has(s.codec_name ?? ""),
  };
}

const TONEMAP =
  "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709," +
  "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p";

/**
 * Extract one frame as JPEG, optionally with a filter applied (grade preview),
 * cached on disk under <editDir>/.studio_cache/frames/.
 */
export async function extractFrame(opts: {
  video: string;
  t: number;
  vf?: string;
  width?: number;
  cacheDir: string;
  hdr?: boolean;
}): Promise<string> {
  const { video, t, vf, width, cacheDir, hdr } = opts;
  const key = crypto
    .createHash("sha1")
    .update([video, t.toFixed(2), vf ?? "", width ?? 0, fs.statSync(video).mtimeMs].join("|"))
    .digest("hex");
  const out = path.join(cacheDir, `${key}.jpg`);
  if (fs.existsSync(out)) return out;
  fs.mkdirSync(cacheDir, { recursive: true });

  const parts: string[] = [];
  if (hdr) parts.push(TONEMAP);
  if (vf) parts.push(vf);
  parts.push(width ? `scale=${width}:-2` : "scale='min(1280,iw)':-2");

  await pexec(
    "ffmpeg",
    [
      "-y", "-ss", t.toFixed(3), "-i", video,
      "-frames:v", "1", "-vf", parts.join(","),
      "-q:v", "4", out,
    ],
    { env: jobEnv(), maxBuffer: 16 * 1024 * 1024 }
  );
  return out;
}
