#!/usr/bin/env python3
"""Check every vertical clip in an episode has its full set of staged assets.

    check_clip_assets.py --episode-dir <Content/DATE-podcast>

For each shorts/<slug>/ that has an mp4, requires:
  - <slug>.mp4 at 1080x1920 with video and audio
  - <slug>-cover.png|jpg, 9:16 within 1% and >= 1000px wide (jbs-adhoc-cover, platform tiktok, returns ~1076x1927)
  - <slug>-post.md with a TikTok caption and an Instagram Reels caption inside the length limits,
    3-6 hashtags each, a Keywords section, and a front-loaded keyword (one of the Keywords appears
    in the first ~125 characters). A leftover episode-link placeholder is allowed (Joe fills it).
Exit code 1 if anything fails. Limits come from shorts_config.json.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "shorts_config.json").read_text())


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height",
                          "-of", "json", str(path)], capture_output=True, text=True)
    try:
        return json.loads(out.stdout).get("streams", [])
    except json.JSONDecodeError:
        return []


def section(text, title):
    m = re.search(rf"^## {re.escape(title)}[^\n]*\n\n(.*?)(?=\n## |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else None


def check_post(text, problems, slug):
    p = CFG["post"]
    kw_text = section(text, "Keywords")
    keywords = [k.strip().lower() for k in (kw_text or "").split(",") if k.strip()]
    if not keywords:
        problems.append(f"{slug}: post.md has no Keywords section")
    for title, limit in (("TikTok caption", p["tiktok_max_chars"]), ("Instagram Reels caption", p["instagram_max_chars"])):
        body = section(text, title)
        if not body:
            problems.append(f"{slug}: post.md is missing '## {title}'")
            continue
        if len(body) > limit:
            problems.append(f"{slug}: {title} is {len(body)} chars (max {limit})")
        tags = re.findall(r"#\w+", body)
        if not (p["hashtags_min"] <= len(tags) <= p["hashtags_max"]):
            problems.append(f"{slug}: {title} has {len(tags)} hashtags (want {p['hashtags_min']}-{p['hashtags_max']})")
        head = body[: p["front_load_chars"]].lower()
        if keywords and not any(k.split()[0] in head for k in keywords):
            problems.append(f"{slug}: {title} has none of its keywords in the first {p['front_load_chars']} chars")
        m = re.search(r"\(\d+ chars\)", text[text.find("## " + title):][:80])
        if m and f"({len(body)} chars)" != m.group(0):
            problems.append(f"{slug}: stated length {m.group(0)} does not match actual {len(body)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode-dir", required=True)
    args = ap.parse_args()
    root = Path(args.episode_dir) / CFG["output"]["dir_name"]
    problems, checked = [], 0
    for d in sorted(x for x in root.iterdir() if x.is_dir()):
        slug = d.name
        mp4 = d / f"{slug}.mp4"
        if not mp4.exists():
            continue
        checked += 1
        s = probe(mp4)
        v = next((x for x in s if x["codec_type"] == "video"), None)
        if not v or (v["width"], v["height"]) != (CFG["canvas"]["width"], CFG["canvas"]["height"]):
            problems.append(f"{slug}: mp4 is not {CFG['canvas']['width']}x{CFG['canvas']['height']}")
        if not any(x["codec_type"] == "audio" for x in s):
            problems.append(f"{slug}: mp4 has no audio stream")
        covers = [c for c in (d / f"{slug}-cover.png", d / f"{slug}-cover.jpg") if c.exists() and c.stat().st_size > 0]
        if not covers:
            problems.append(f"{slug}: cover image missing ({slug}-cover.png)")
        else:
            cs = next((x for x in probe(covers[0]) if x["codec_type"] == "video"), None)
            cc = CFG["cover"]
            target = cc["width"] / cc["height"]
            if (not cs or cs["width"] < cc["min_width"]
                    or abs(cs["width"] / cs["height"] - target) / target > cc["aspect_tolerance"]):
                got = f"{cs['width']}x{cs['height']}" if cs else "unreadable"
                problems.append(f"{slug}: cover is {got}, want 9:16 within {cc['aspect_tolerance']:.0%} and >= {cc['min_width']}px wide (platform tiktok)")
        post = d / f"{slug}-post.md"
        if not post.exists():
            problems.append(f"{slug}: {slug}-post.md missing")
        else:
            check_post(post.read_text(), problems, slug)
    if not checked:
        print("no clips found")
        return 1
    for pr in problems:
        print("FAIL", pr)
    print(f"{checked} clip(s) checked, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
