#!/usr/bin/env python3
"""
Generate B-Roll — builds a HyperFrames talking-head-recut composition for a
podcast episode: an intro title card (burned in for the spoken intro, fading
out right as the dialogue starts), speaker-isolated karaoke captions (burned
in for the dialogue, one speaker's turn visible at a time, teal highlight box
per active word), and hand-authored B-roll cards (topic-marker / stat /
stat-warning / stat-dual / quote / thesis / outro / icon-badge / chat-sim),
all in the established JBS "jbs-custom" theme.

This is the reusable form of the one-off generator scripts first written for
Content/2026-07-27-podcast/hf-broll/ and Content/2026-07-28-podcast/hf-broll/.
Card *content* is still hand-authored per episode (picking the right stat /
quote / topic-marker moments is a judgment call) — this script handles
everything mechanical: asset staging, video re-encoding, title card, karaoke
captions from the transcript, and assembling it all into index.html.

Two-pass workflow:

  1. Stage the project (copies fonts/vendor/images from the shared asset
     library, re-encodes the source video for seekable rendering, and writes
     a storyboard.json skeleton if one doesn't exist yet):

       python3 generate_broll.py stage \\
           --episode-dir /path/to/Content/2026-MM-DD-podcast \\
           --video edit/daily-ai-pulse-2026-MM-DD-final.mp4

  2. Hand-author (or ask Claude to draft, from the transcript/brief/chapters)
     the cards[] array in <episode-dir>/hf-broll/storyboard.json — same
     schema as previous episodes: id, archetype, startSec, endSec,
     accentIndex (0-4), zone ("video-overlay"), contentHints.

  3. Build the composition (title card + captions + your authored cards):

       python3 generate_broll.py build \\
           --episode-dir /path/to/Content/2026-MM-DD-podcast \\
           --title "Episode Title Here"

     --content-start (seconds) defaults to edit/intro_meta.json's
     content_start, written automatically by build_video.py's intro step.
     Pass --content-start explicitly to override.

  4. Render:

       cd /path/to/Content/2026-MM-DD-podcast/hf-broll
       PRODUCER_BROWSER_GPU_MODE=hardware npx hyperframes render public \\
           --skill=talking-head-recut -o output.mp4 --fps 24

     Or pass --render to have step 3 do this automatically.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
ASSETS_DIR = SKILL_DIR / "hf-broll-assets"

TITLE_KICKER_TEMPLATE = "DAILY AI PULSE · {date}"

MAX_WORDS_PER_CHUNK = 8
MIN_WORDS_FOR_PUNCT_BREAK = 4

THEME = {
    "bg": "#1B2A3B",
    "card-bg": "#0F1C2B",
    "accent-0": "#4DD9C0",
    "accent-1": "#5BCFEA",
    "accent-2": "#8B9FD4",
    "accent-3": "#E8590C",
    "accent-4": "#9C36B5",
    "text": "#FFFFFF",
    "text-light": "#A8B8CC",
}

# Minimal flat-icon library for icon-badge / chat-sim cards — inline SVG so
# there's no external asset dependency. Keep additions in this same visual
# language (single-color glyph, 24x24 viewBox, currentColor fill).
ICON_LIBRARY = {
    "robot": '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="12" cy="3.5" r="1.3" fill="#0F1C2B"/>
      <line x1="12" y1="4.8" x2="12" y2="7" stroke="#0F1C2B" stroke-width="1.4"/>
      <rect x="4" y="7" width="16" height="12" rx="4" fill="#0F1C2B"/>
      <circle cx="9" cy="13" r="1.8" fill="#FFEB3B"/>
      <circle cx="15" cy="13" r="1.8" fill="#FFEB3B"/>
      <rect x="8.5" y="16.4" width="7" height="1.6" rx="0.8" fill="#FFEB3B"/>
    </svg>''',
    "person": '''<svg viewBox="0 0 24 24" fill="#0F1C2B" xmlns="http://www.w3.org/2000/svg">
      <circle cx="12" cy="7" r="4.2"/>
      <path d="M4 20.5c0-4.4 3.6-8 8-8s8 3.6 8 8v.5H4v-.5z"/>
    </svg>''',
    "alert": '''<svg viewBox="0 0 24 24" fill="#0F1C2B" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2 L22.5 21 H1.5 Z"/>
      <rect x="11" y="9" width="2" height="6.5" rx="1" fill="#FFEB3B"/>
      <circle cx="12" cy="18" r="1.1" fill="#FFEB3B"/>
    </svg>''',
    "chat": '''<svg viewBox="0 0 24 24" fill="#0F1C2B" xmlns="http://www.w3.org/2000/svg">
      <path d="M3 5h18a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9l-5 4v-4H3a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z"/>
    </svg>''',
    "calendar": '''<svg viewBox="0 0 24 24" fill="#0F1C2B" xmlns="http://www.w3.org/2000/svg">
      <rect x="3" y="4" width="18" height="17" rx="2"/>
      <rect x="3" y="4" width="18" height="4" rx="2" fill="#FFEB3B"/>
      <rect x="7" y="1.5" width="2" height="4" rx="1" fill="#0F1C2B"/>
      <rect x="15" y="1.5" width="2" height="4" rx="1" fill="#0F1C2B"/>
    </svg>''',
}


# Two supported delivery formats. All card archetypes position themselves
# relative to W/H (panels flush to the bottom edge, chat-sim covers the full
# frame), so switching format is just picking a preset — no per-archetype
# rework needed. Pass --format to `stage` to pick; landscape stays the
# default for existing long-form podcast recuts.
FORMAT_PRESETS = {
    "landscape": {"width": 1920, "height": 1080, "fps": 24, "layout": "landscape"},
    "portrait": {"width": 1080, "height": 1920, "fps": 30, "layout": "portrait"},
}

STORYBOARD_SKELETON = {
    "schemaVersion": 3,
    "composition": {
        "fps": 24,
        "width": 1920,
        "height": 1080,
        "durationSeconds": None,
        "layout": "landscape",
        "themeId": "jbs-custom",
        "seed": 0,
    },
    "videoTrack": {
        "sourcePath": "input-video.mp4",
        "startSec": 0,
        "endSec": None,
        "bounds": {"x": 0, "y": 0, "width": 1920, "height": 1080},
    },
    "subtitles": {"enabled": False},
    "cards": [],
}


# --------------------------------------------------------------------- stage
def stage(args):
    episode_dir = Path(args.episode_dir).resolve()
    project = episode_dir / "hf-broll"
    public = project / "public"
    for sub in ["fonts", "vendor", "images", "cards"]:
        (public / sub).mkdir(parents=True, exist_ok=True)

    for f in (ASSETS_DIR / "fonts").glob("*"):
        shutil.copy(f, public / "fonts" / f.name)
    shutil.copy(ASSETS_DIR / "vendor" / "gsap.min.js", public / "vendor" / "gsap.min.js")
    for f in (ASSETS_DIR / "images").glob("*"):
        shutil.copy(f, public / "images" / f.name)
    print(f"[info] staged fonts/vendor/images -> {public}")

    video_path = Path(args.video)
    if not video_path.is_absolute():
        video_path = episode_dir / video_path
    if not video_path.exists():
        sys.exit(f"[error] video not found: {video_path}")

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-show_entries", "format=duration",
         "-of", "json", str(video_path)],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(probe.stdout)
    duration = float(info["format"]["duration"])
    src_w = info["streams"][0]["width"]
    src_h = info["streams"][0]["height"]

    preset = FORMAT_PRESETS[args.format]
    W, H = preset["width"], preset["height"]
    fps = args.fps or preset["fps"]

    staged_video = public / "input-video.mp4"
    if (src_w, src_h) == (W, H):
        scale_filter = None
    else:
        # crop-to-fill: scale up so the shorter side matches the target, then
        # center-crop the overflow. Keeps a talking-head subject roughly
        # centered; re-frame manually in the source if that's not true here.
        scale_filter = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
        print(f"[info] source is {src_w}x{src_h}, target is {W}x{H} ({args.format}) "
              f"-> center-crop applied. Re-crop the source yourself first if the "
              f"subject isn't centered.")

    ffmpeg_cmd = ["ffmpeg", "-y", "-i", str(video_path)]
    if scale_filter:
        ffmpeg_cmd += ["-vf", scale_filter]
    ffmpeg_cmd += [
        "-c:v", "libx264", "-crf", "18", "-g", str(fps), "-keyint_min", str(fps),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-c:a", "aac",
        str(staged_video),
    ]
    subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
    print(f"[info] re-encoded video ({duration:.1f}s, {W}x{H}@{fps}) -> {staged_video}")

    storyboard_path = project / "storyboard.json"
    if storyboard_path.exists():
        print(f"[info] storyboard.json already exists, leaving it alone: {storyboard_path}")
    else:
        skeleton = json.loads(json.dumps(STORYBOARD_SKELETON))
        skeleton["composition"]["durationSeconds"] = round(duration, 4)
        skeleton["composition"]["fps"] = fps
        skeleton["composition"]["width"] = W
        skeleton["composition"]["height"] = H
        skeleton["composition"]["layout"] = preset["layout"]
        skeleton["videoTrack"]["endSec"] = round(duration, 4)
        skeleton["videoTrack"]["bounds"] = {"x": 0, "y": 0, "width": W, "height": H}
        storyboard_path.write_text(json.dumps(skeleton, indent=2))
        print(f"[info] wrote storyboard skeleton ({args.format}, {W}x{H}) -> {storyboard_path}")
        print("[info] now hand-author cards[] (topic-marker / stat / stat-warning / "
              "stat-dual / quote / thesis / outro / icon-badge / chat-sim) before "
              "running --build")


# ---------------------------------------------------------------- fst helpers
def q(t, fps):
    return round(round(t * fps) / fps, 4)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def chars(s):
    out = []
    for ch in s:
        c = "&nbsp;" if ch == " " else ch
        out.append(f'<span class="char">{c}</span>')
    return "".join(out)


# ------------------------------------------------------------ card archetypes
def card_shell(cid, style_extra, body, accent):
    css = f'''<div class="card" data-card-id="{cid}">
  <style>

    .card[data-card-id="{cid}"] .root {{
      width: 100%; height: 100%; position: relative; font-family: 'Inter', sans-serif;
    }}

      .panel {{
        background: rgba(15,28,43,0.96);
        border-top: 2px solid var(--accent-{accent});
        box-shadow: 0 -8px 40px rgba(77,217,192,0.18), 0 -1px 0 rgba(77,217,192,0.4);
        display: flex;
        align-items: center;
        padding: 0 90px;
        box-sizing: border-box;
      }}
      .corner {{
        position: absolute; width: 34px; height: 34px;
        border-color: var(--accent-{accent});
        opacity: 0.55;
      }}
      .corner-tl {{ left: 28px; top: 22px; border-left: 2px solid; border-top: 2px solid; }}
      .corner-tr {{ right: 28px; top: 22px; border-right: 2px solid; border-top: 2px solid; }}

{style_extra}
  </style>
  <div class="root">

{body}

  </div>
</div>'''
    return css


def build_topic_marker(card, accent, W, H=1080):
    cid = card["id"]
    h = card["contentHints"]
    style_extra = f'''    .card[data-card-id="{cid}"] .kicker {{
      font-family: 'SF Mono', 'Inter', monospace; font-size: 22px; letter-spacing: 4px; text-transform: uppercase;
      color: var(--accent-{accent}); margin-bottom: 14px; font-weight: 700;
    }}
    .card[data-card-id="{cid}"] .title {{
      font-family: 'SF Pro Rounded', 'Inter', sans-serif; font-size: 76px; font-weight: 800; color: #FFFFFF;
      margin: 0 0 10px 0; line-height: 1.02;
    }}
    .card[data-card-id="{cid}"] .detail {{
      font-family: 'Inter', sans-serif; font-size: 30px; color: var(--text-light); font-weight: 400;
    }}
    .card[data-card-id="{cid}"] .rule {{
      width: 0; height: 3px; background: var(--accent-{accent}); border-radius: 2px; margin: 18px 0 0 0;
    }}'''
    body = f'''    <div class="panel " style="position:absolute; left:0; top:{H-260}px; width:{W}px; height:260px;">
      <div class="corner corner-tl"></div>
      <div class="corner corner-tr"></div>

      <div class="content">
        <div class="kicker" id="{cid}-kicker" data-anim="fade-in" data-anim-at="0.05" data-anim-duration="0.22">{esc(h['kicker'])}</div>
        <h1 class="title" id="{cid}-title" data-anim="kinetic-chars" data-anim-at="0.18" data-anim-duration="0.4" data-anim-stagger="0.02" data-anim-pattern="pop">{chars(h['title'])}</h1>
        <div class="detail" id="{cid}-detail" data-anim="fade-in" data-anim-at="0.5" data-anim-duration="0.25">{esc(h['detail'])}</div>
        <div class="rule" id="{cid}-rule" data-anim="grow-x" data-anim-at="0.3" data-anim-duration="0.35" data-anim-target-w="140"></div>
      </div>
    </div>'''
    return card_shell(cid, style_extra, body, accent)


def build_stat(card, accent, W, H=1080):
    cid = card["id"]
    h = card["contentHints"]
    style_extra = f'''    .card[data-card-id="{cid}"] .value {{
      font-family: 'SF Mono', 'Inter', monospace; font-size: 108px; font-weight: 700; color: #FFFFFF;
      line-height: 1; margin-right: 56px; white-space: nowrap;
    }}
    .card[data-card-id="{cid}"] .divider {{
      width: 2px; align-self: stretch; background: rgba(168,184,204,0.25); margin-right: 56px;
    }}
    .card[data-card-id="{cid}"] .label {{
      font-family: 'Inter', sans-serif; font-size: 32px; color: var(--text-light); max-width: 640px; line-height: 1.28;
    }}
    .card[data-card-id="{cid}"] .row {{ display: flex; align-items: center; }}'''
    body = f'''    <div class="panel " style="position:absolute; left:0; top:{H-320}px; width:{W}px; height:320px;">
      <div class="corner corner-tl"></div>
      <div class="corner corner-tr"></div>

      <div class="content">
        <div class="row">
          <div class="value" id="{cid}-value" data-anim="scale-pop" data-anim-at="0.1" data-anim-duration="0.4">{esc(h['value'])}</div>
          <div class="divider"></div>
          <div class="label" id="{cid}-label" data-anim="fade-in" data-anim-at="0.35" data-anim-duration="0.3">{esc(h['label'])}</div>
        </div>
      </div>
    </div>'''
    return card_shell(cid, style_extra, body, accent)


def build_stat_warning(card, accent, W, H=1080):
    cid = card["id"]
    h = card["contentHints"]
    style_extra = f'''    .card[data-card-id="{cid}"] .value {{
      font-family: 'SF Mono', 'Inter', monospace; font-size: 108px; font-weight: 700; color: #FFFFFF;
      line-height: 1; margin-right: 56px; white-space: nowrap;
    }}
    .card[data-card-id="{cid}"] .divider {{
      width: 2px; align-self: stretch; background: rgba(168,184,204,0.25); margin-right: 56px;
    }}
    .card[data-card-id="{cid}"] .label {{
      font-family: 'Inter', sans-serif; font-size: 32px; color: var(--text-light); max-width: 640px; line-height: 1.28;
    }}
    .card[data-card-id="{cid}"] .row {{ display: flex; align-items: center; }}
    .card[data-card-id="{cid}"] .tag {{
      font-family: 'SF Mono', 'Inter', monospace; font-size: 20px; letter-spacing: 2px; font-weight: 700;
      color: var(--accent-{accent}); background: rgba(139,159,212,0.12); border: 1px solid var(--accent-{accent});
      display: inline-block; padding: 8px 16px; border-radius: 6px; margin-top: 16px;
    }}'''
    body = f'''    <div class="panel " style="position:absolute; left:0; top:{H-360}px; width:{W}px; height:360px;">
      <div class="corner corner-tl"></div>
      <div class="corner corner-tr"></div>

      <div class="content">
        <div class="row">
          <div class="value" id="{cid}-value" data-anim="scale-pop" data-anim-at="0.1" data-anim-duration="0.4">{esc(h['value'])}</div>
          <div class="divider"></div>
          <div class="label" id="{cid}-label" data-anim="fade-in" data-anim-at="0.35" data-anim-duration="0.3">{esc(h['label'])}<div class="tag" id="{cid}-tag" data-anim="fade-in" data-anim-at="0.55" data-anim-duration="0.22">{esc(h['tag'])}</div></div>
        </div>
      </div>
    </div>'''
    return card_shell(cid, style_extra, body, accent)


def build_stat_dual(card, accent, W, H=1080):
    cid = card["id"]
    h = card["contentHints"]
    style_extra = f'''    .card[data-card-id="{cid}"] .stat-block {{ text-align: center; }}
    .card[data-card-id="{cid}"] .stat-block .num {{
      font-family: 'SF Mono', 'Inter', monospace; font-size: 92px; font-weight: 700; line-height: 1;
    }}
    .card[data-card-id="{cid}"] .stat-block .lbl {{
      font-family: 'Inter', sans-serif; font-size: 24px; color: var(--text-light); margin-top: 10px;
    }}
    .card[data-card-id="{cid}"] .numA {{ color: var(--accent-{accent}); }}
    .card[data-card-id="{cid}"] .numB {{ color: var(--text-light); opacity: 0.6; }}
    .card[data-card-id="{cid}"] .vs {{
      font-family: 'SF Mono', 'Inter', monospace; font-size: 28px; color: var(--text-light); opacity: 0.5;
      margin: 0 70px; align-self: center;
    }}
    .card[data-card-id="{cid}"] .row {{ display: flex; align-items: center; justify-content: center; width: 100%; }}'''
    body = f'''    <div class="panel " style="position:absolute; left:0; top:{H-320}px; width:{W}px; height:320px;">
      <div class="corner corner-tl"></div>
      <div class="corner corner-tr"></div>

      <div class="content" style="width:100%;">
        <div class="row">
          <div class="stat-block" id="{cid}-a" data-anim="scale-pop" data-anim-at="0.1" data-anim-duration="0.4">
            <div class="num numA">{esc(h['valueA'])}</div>
            <div class="lbl">{esc(h['labelA'])}</div>
          </div>
          <div class="vs" id="{cid}-vs" data-anim="fade-in" data-anim-at="0.3" data-anim-duration="0.2">VS</div>
          <div class="stat-block" id="{cid}-b" data-anim="scale-pop" data-anim-at="0.42" data-anim-duration="0.4">
            <div class="num numB">{esc(h['valueB'])}</div>
            <div class="lbl">{esc(h['labelB'])}</div>
          </div>
        </div>
      </div>
    </div>'''
    return card_shell(cid, style_extra, body, accent)


def build_quote(card, accent, W, H=1080):
    cid = card["id"]
    h = card["contentHints"]
    style_extra = f'''    .card[data-card-id="{cid}"] .quote-mark {{
      font-family: 'SF Pro Rounded', 'Inter', sans-serif; font-size: 90px; color: var(--accent-{accent}); opacity: 0.5;
      line-height: 1; margin-right: 30px;
    }}
    .card[data-card-id="{cid}"] .quote-text {{
      font-family: 'SF Pro Rounded', 'Inter', sans-serif; font-size: 54px; font-weight: 700; color: #FFFFFF;
      line-height: 1.18; max-width: 1350px;
    }}
    .card[data-card-id="{cid}"] .row {{ display: flex; align-items: center; }}'''
    body = f'''    <div class="panel " style="position:absolute; left:0; top:{H-260}px; width:{W}px; height:260px;">
      <div class="corner corner-tl"></div>
      <div class="corner corner-tr"></div>

      <div class="content">
        <div class="row">
          <div class="quote-mark">&ldquo;</div>
          <div class="quote-text" id="{cid}-text" data-anim="fade-in" data-anim-at="0.12" data-anim-duration="0.4">{esc(h['quote'])}</div>
        </div>
      </div>
    </div>'''
    return card_shell(cid, style_extra, body, accent)


def build_thesis(card, accent, W, H=1080):
    cid = card["id"]
    h = card["contentHints"]
    style_extra = f'''    .card[data-card-id="{cid}"] .col {{
      flex: 1; padding: 0 40px;
    }}
    .card[data-card-id="{cid}"] .col-sep {{
      width: 2px; align-self: stretch; background: rgba(168,184,204,0.25); margin: 30px 0;
    }}
    .card[data-card-id="{cid}"] .col-label {{
      font-family: 'SF Mono', 'Inter', monospace; font-size: 42px; font-weight: 700; letter-spacing: 3px; margin-bottom: 18px;
    }}
    .card[data-card-id="{cid}"] .col-label.build {{ color: var(--accent-0); }}
    .card[data-card-id="{cid}"] .col-label.buy {{ color: var(--accent-2); }}
    .card[data-card-id="{cid}"] .col-detail {{
      font-family: 'Inter', sans-serif; font-size: 27px; color: var(--text-light); line-height: 1.35; max-width: 560px;
    }}
    .card[data-card-id="{cid}"] .row {{ display: flex; align-items: center; width: 100%; }}'''
    body = f'''    <div class="panel " style="position:absolute; left:0; top:{H-420}px; width:{W}px; height:420px;">
      <div class="corner corner-tl"></div>
      <div class="corner corner-tr"></div>

      <div class="content" style="width:100%;">
        <div class="row">
          <div class="col" id="{cid}-build" data-anim="slide-in" data-anim-at="0.08" data-anim-duration="0.35" data-anim-from="left" data-anim-distance="60">
            <div class="col-label build">{esc(h['buildLabel'])}</div>
            <div class="col-detail">{esc(h['buildDetail'])}</div>
          </div>
          <div class="col-sep"></div>
          <div class="col" id="{cid}-buy" data-anim="slide-in" data-anim-at="0.22" data-anim-duration="0.35" data-anim-from="right" data-anim-distance="60">
            <div class="col-label buy">{esc(h['buyLabel'])}</div>
            <div class="col-detail">{esc(h['buyDetail'])}</div>
          </div>
        </div>
      </div>
    </div>'''
    return card_shell(cid, style_extra, body, accent)


def build_outro(card, accent, W, H=1080):
    cid = card["id"]
    h = card["contentHints"]
    return f'''<div class="card" data-card-id="{cid}">
  <style>
    .card[data-card-id="{cid}"] .root {{
      width: 100%; height: 100%; position: relative; font-family: 'Inter', sans-serif;
      display: flex; align-items: center; justify-content: center;
      background: rgba(27,42,59,0.92);
    }}
    .card[data-card-id="{cid}"] .center {{ text-align: center; }}
    .card[data-card-id="{cid}"] .wordmark {{ height: 260px; margin-bottom: 30px; }}
    .card[data-card-id="{cid}"] .tagline {{
      font-family: 'SF Mono', 'Inter', monospace; font-size: 36px; letter-spacing: 4px; color: var(--accent-{accent});
      text-transform: uppercase; font-weight: 700;
    }}
  </style>
  <div class="root">

    <div class="center">
      <img class="wordmark" id="{cid}-wordmark" src="images/jbs-wordmark-color.png" data-anim="fade-in" data-anim-at="0.1" data-anim-duration="0.4" />
      <div class="tagline" id="{cid}-tagline" data-anim="fade-in" data-anim-at="0.4" data-anim-duration="0.35">{esc(h['tagline'])}</div>
    </div>

  </div>
</div>'''


def build_icon_badge(card, accent, W, H=1080):
    """Small circular icon that pops in near a keyword, sitting on top of the
    live video (not a fullscreen takeover) — the "robot icon flashes when she
    says AI" effect. contentHints: icon (see ICON_LIBRARY), x/y (px, center
    anchor, defaults top-right), size (px, default 140)."""
    cid = card["id"]
    h = card["contentHints"]
    icon = h.get("icon", "robot")
    size = h.get("size", 140)
    cx = h.get("x", W - 160)
    cy = h.get("y", 220)
    left = cx - size / 2
    top = cy - size / 2
    style_extra = f'''    .card[data-card-id="{cid}"] .badge {{
      position: absolute; left: {left}px; top: {top}px; width: {size}px; height: {size}px;
      border-radius: 50%; background: var(--accent-{accent});
      display: flex; align-items: center; justify-content: center;
      box-shadow: 0 10px 28px rgba(0,0,0,0.4);
      transform: scale(0); transform-origin: center;
    }}
    .card[data-card-id="{cid}"] .badge svg {{ width: 60%; height: 60%; }}'''
    body = f'''    <div class="badge" id="{cid}-badge">{ICON_LIBRARY.get(icon, ICON_LIBRARY["robot"])}</div>'''
    return f'''<div class="card" data-card-id="{cid}">
  <style>
    .card[data-card-id="{cid}"] .root {{ width:100%; height:100%; position:relative; }}
{style_extra}
  </style>
  <div class="root">
{body}
  </div>
</div>'''


def build_chat_sim(card, accent, W, H):
    """Fullscreen cutaway: dark radial-gradient background, one or two avatar
    circles (icon library), an optional 'typing' speech bubble on the active
    speaker, and a caption line underneath — the simulated
    chat/notification-exchange scene used to visually narrate a hypothetical.
    contentHints: leftAvatar, rightAvatar (icon names, either optional),
    activeSpeaker ("left"|"right", gets the typing bubble), line (caption)."""
    cid = card["id"]
    h = card["contentHints"]
    left_icon = h.get("leftAvatar")
    right_icon = h.get("rightAvatar")
    active = h.get("activeSpeaker", "right")
    line = h.get("line", "")
    style_extra = f'''    .card[data-card-id="{cid}"] .root {{
      width:100%; height:100%; position:relative;
      background: radial-gradient(circle at 50% 28%, #3a0808 0%, #150202 75%);
    }}
    .card[data-card-id="{cid}"] .avatar {{
      position:absolute; width:22%; max-width:220px; aspect-ratio:1/1; border-radius:50%;
      background: var(--accent-{accent}); display:flex; align-items:center; justify-content:center;
      transform: scale(0); transform-origin:center;
    }}
    .card[data-card-id="{cid}"] .avatar svg {{ width:56%; height:56%; }}
    .card[data-card-id="{cid}"] .avatar-left {{ left:12%; top:38%; }}
    .card[data-card-id="{cid}"] .avatar-right {{ right:14%; top:22%; }}
    .card[data-card-id="{cid}"] .bubble {{
      position:absolute; width:100px; height:56px; border-radius:28px; background:#E8E8E8;
      display:flex; align-items:center; justify-content:center; gap:9px; opacity:0;
    }}
    .card[data-card-id="{cid}"] .bubble span {{ width:12px; height:12px; border-radius:50%; background:#8a8a8a; }}
    .card[data-card-id="{cid}"] .caption {{
      position:absolute; left:8%; right:8%; bottom:30%; text-align:center;
      font-family:'Inter', sans-serif; font-weight:700; font-size:44px; color:#EDEDED;
      opacity:0;
    }}'''
    avatars = ""
    if left_icon:
        avatars += f'<div class="avatar avatar-left" id="{cid}-left">{ICON_LIBRARY.get(left_icon, ICON_LIBRARY["person"])}</div>\n    '
    if right_icon:
        avatars += f'<div class="avatar avatar-right" id="{cid}-right">{ICON_LIBRARY.get(right_icon, ICON_LIBRARY["robot"])}</div>\n    '
    bubble_pos = "right:6%; top:8%;" if active == "right" else "left:6%; top:24%;"
    body = f'''    {avatars}<div class="bubble" id="{cid}-bubble" style="{bubble_pos}">
      <span></span><span></span><span></span>
    </div>
    <div class="caption" id="{cid}-caption">{esc(line)}</div>'''
    return f'''<div class="card" data-card-id="{cid}">
  <style>
{style_extra}
  </style>
  <div class="root">
{body}
  </div>
</div>'''


BUILDERS = {
    "topic-marker": build_topic_marker,
    "stat": build_stat,
    "stat-warning": build_stat_warning,
    "stat-dual": build_stat_dual,
    "quote": build_quote,
    "thesis": build_thesis,
    "outro": build_outro,
    "icon-badge": build_icon_badge,
    "chat-sim": build_chat_sim,
}


def card_gsap(card, fps):
    cid = card["id"]
    arch = card["archetype"]
    start = q(card["startSec"], fps)
    end = q(card["endSec"], fps)
    fade_out_start = q(max(start, end - 0.28), fps)
    lines = [f"          // ---- {cid} [{start}s -> {end}s] ----"]
    lines.append(f"          tl.set('.card-host[data-card-id=\"{cid}\"]', {{visibility:'visible'}}, {start});")
    lines.append(f"          tl.fromTo('.card-host[data-card-id=\"{cid}\"]', {{opacity:0}}, {{opacity:1, duration:0.28, ease:'power2.out'}}, {start});")

    if card.get("zone") == "fullscreen":
        lines.append(f"          tl.to('#video-wrap', {{opacity:0, duration:0.2, ease:'power2.out'}}, {start});")

    if arch == "topic-marker":
        lines.append(f"          tl.fromTo('.card[data-card-id=\"{cid}\"] #{cid}-kicker', {{opacity:0}}, {{opacity:1, duration:0.22, ease:'power2.out'}}, {q(start+0.0417, fps)});")
        lines.append(f"          tl.from('.card[data-card-id=\"{cid}\"] #{cid}-title .char', {{opacity:0, y:8, scale:0.85, duration:0.4, ease:'power2.out', stagger:0.02}}, {q(start+0.1667, fps)});")
        lines.append(f"          tl.fromTo('.card[data-card-id=\"{cid}\"] #{cid}-detail', {{opacity:0}}, {{opacity:1, duration:0.25, ease:'power2.out'}}, {q(start+0.5, fps)});")
        lines.append(f"          tl.fromTo('.card[data-card-id=\"{cid}\"] #{cid}-rule', {{width:0}}, {{width:140, duration:0.35, ease:'power2.out'}}, {q(start+0.3, fps)});")
    elif arch in ("stat", "stat-warning"):
        lines.append(f"          tl.fromTo('.card[data-card-id=\"{cid}\"] #{cid}-value', {{opacity:0, scale:0.6}}, {{opacity:1, scale:1, duration:0.4, ease:'back.out(1.6)'}}, {q(start+0.0833, fps)});")
        lines.append(f"          tl.fromTo('.card[data-card-id=\"{cid}\"] #{cid}-label', {{opacity:0}}, {{opacity:1, duration:0.3, ease:'power2.out'}}, {q(start+0.3333, fps)});")
    elif arch == "stat-dual":
        lines.append(f"          tl.fromTo('.card[data-card-id=\"{cid}\"] #{cid}-a', {{opacity:0, scale:0.6}}, {{opacity:1, scale:1, duration:0.4, ease:'back.out(1.6)'}}, {q(start+0.1, fps)});")
        lines.append(f"          tl.fromTo('.card[data-card-id=\"{cid}\"] #{cid}-vs', {{opacity:0}}, {{opacity:1, duration:0.2, ease:'power2.out'}}, {q(start+0.3, fps)});")
        lines.append(f"          tl.fromTo('.card[data-card-id=\"{cid}\"] #{cid}-b', {{opacity:0, scale:0.6}}, {{opacity:1, scale:1, duration:0.4, ease:'back.out(1.6)'}}, {q(start+0.42, fps)});")
    elif arch == "quote":
        lines.append(f"          tl.fromTo('.card[data-card-id=\"{cid}\"] #{cid}-text', {{opacity:0}}, {{opacity:1, duration:0.4, ease:'power2.out'}}, {q(start+0.12, fps)});")
    elif arch == "thesis":
        lines.append(f"          tl.fromTo('.card[data-card-id=\"{cid}\"] #{cid}-build', {{opacity:0, x:-60}}, {{opacity:1, x:0, duration:0.35, ease:'power2.out'}}, {q(start+0.08, fps)});")
        lines.append(f"          tl.fromTo('.card[data-card-id=\"{cid}\"] #{cid}-buy', {{opacity:0, x:60}}, {{opacity:1, x:0, duration:0.35, ease:'power2.out'}}, {q(start+0.22, fps)});")
    elif arch == "outro":
        lines.append(f"          tl.fromTo('.card[data-card-id=\"{cid}\"] #{cid}-wordmark', {{opacity:0}}, {{opacity:1, duration:0.4, ease:'power2.out'}}, {q(start+0.1, fps)});")
        lines.append(f"          tl.fromTo('.card[data-card-id=\"{cid}\"] #{cid}-tagline', {{opacity:0}}, {{opacity:1, duration:0.35, ease:'power2.out'}}, {q(start+0.4, fps)});")
    elif arch == "icon-badge":
        lines.append(f"          tl.fromTo('.card[data-card-id=\"{cid}\"] #{cid}-badge', {{scale:0}}, {{scale:1, duration:0.3, ease:'back.out(2.2)'}}, {q(start+0.05, fps)});")
        lines.append(f"          tl.to('.card[data-card-id=\"{cid}\"] #{cid}-badge', {{scale:0, duration:0.2, ease:'power2.in'}}, {fade_out_start});")
    elif arch == "chat-sim":
        h = card["contentHints"]
        if h.get("leftAvatar"):
            lines.append(f"          tl.fromTo('.card[data-card-id=\"{cid}\"] #{cid}-left', {{scale:0}}, {{scale:1, duration:0.35, ease:'back.out(1.7)'}}, {q(start+0.08, fps)});")
        if h.get("rightAvatar"):
            lines.append(f"          tl.fromTo('.card[data-card-id=\"{cid}\"] #{cid}-right', {{scale:0}}, {{scale:1, duration:0.35, ease:'back.out(1.7)'}}, {q(start+0.22, fps)});")
        lines.append(f"          tl.fromTo('.card[data-card-id=\"{cid}\"] #{cid}-bubble', {{opacity:0, scale:0.6}}, {{opacity:1, scale:1, duration:0.25, ease:'power2.out'}}, {q(start+0.45, fps)});")
        lines.append(f"          tl.to('.card[data-card-id=\"{cid}\"] #{cid}-bubble span', {{y:-6, duration:0.28, ease:'sine.inOut', repeat:-1, yoyo:true, stagger:0.12}}, {q(start+0.5, fps)});")
        lines.append(f"          tl.fromTo('.card[data-card-id=\"{cid}\"] #{cid}-caption', {{opacity:0, y:10}}, {{opacity:1, y:0, duration:0.3, ease:'power2.out'}}, {q(start+0.65, fps)});")

    lines.append(f"          tl.to('.card-host[data-card-id=\"{cid}\"]', {{opacity:0, duration:0.28, ease:'power2.in'}}, {fade_out_start});")
    lines.append(f"          tl.set('.card-host[data-card-id=\"{cid}\"]', {{visibility:'hidden'}}, {end});")
    if card.get("zone") == "fullscreen":
        lines.append(f"          tl.to('#video-wrap', {{opacity:1, duration:0.2, ease:'power2.in'}}, {fade_out_start});")
    lines.append("          ")
    return "\n".join(lines)


# ---------------------------------------------------------------- title card
def build_title_card(title, kicker):
    cid = "title-card"
    return f'''<div class="card" data-card-id="{cid}">
  <style>
    .card[data-card-id="{cid}"] .root {{
      width: 100%; height: 100%; position: relative; font-family: 'Inter', sans-serif;
    }}
    .card[data-card-id="{cid}"] .backdrop {{
      position: absolute; inset: 0; background: rgba(11,18,27,0.58);
    }}
    .card[data-card-id="{cid}"] .center {{
      position: absolute; left: 50%; top: 50%; transform: translate(-50%,-50%);
      text-align: center; max-width: 1500px;
      background: rgba(15,28,43,0.88); border-top: 2px solid var(--accent-0);
      box-shadow: 0 20px 70px rgba(0,0,0,0.5), 0 -1px 0 rgba(77,217,192,0.4);
      padding: 64px 90px;
    }}
    .card[data-card-id="{cid}"] .monogram {{ height: 84px; margin-bottom: 28px; }}
    .card[data-card-id="{cid}"] .kicker {{
      font-family: 'SF Mono', 'Inter', monospace; font-size: 24px; letter-spacing: 4px;
      text-transform: uppercase; color: var(--accent-0); font-weight: 700; margin-bottom: 22px;
    }}
    .card[data-card-id="{cid}"] .title {{
      font-family: 'SF Pro Rounded', 'Inter', sans-serif; font-size: 68px; font-weight: 800;
      color: #FFFFFF; line-height: 1.14; margin: 0;
    }}
    .card[data-card-id="{cid}"] .rule {{
      width: 0; height: 3px; background: var(--accent-0); border-radius: 2px; margin: 28px auto 0;
    }}
  </style>
  <div class="root">
    <div class="backdrop"></div>
    <div class="center">
      <img class="monogram" id="{cid}-monogram" src="images/jbs-monogram.png" data-anim="fade-in" data-anim-at="0.05" data-anim-duration="0.35" />
      <div class="kicker" id="{cid}-kicker" data-anim="fade-in" data-anim-at="0.2" data-anim-duration="0.3">{esc(kicker)}</div>
      <h1 class="title" id="{cid}-title" data-anim="fade-in" data-anim-at="0.35" data-anim-duration="0.45">{esc(title)}</h1>
      <div class="rule" id="{cid}-rule" data-anim="grow-x" data-anim-at="0.5" data-anim-duration="0.4" data-anim-target-w="160"></div>
    </div>
  </div>
</div>'''


def title_gsap(fade_start, end, fps):
    start = q(0.0, fps)
    fade_start = q(fade_start, fps)
    end = q(end, fps)
    lines = [
        f"          // ---- title-card [{start}s -> {end}s] ----",
        f"          tl.set('.card-host[data-card-id=\"title-card\"]', {{visibility:'visible'}}, {start});",
        f"          tl.fromTo('.card-host[data-card-id=\"title-card\"]', {{opacity:0}}, {{opacity:1, duration:0.4, ease:'power2.out'}}, {start});",
        f"          tl.fromTo('#title-card-monogram', {{opacity:0}}, {{opacity:1, duration:0.35, ease:'power2.out'}}, {q(0.15, fps)});",
        f"          tl.fromTo('#title-card-kicker', {{opacity:0}}, {{opacity:1, duration:0.3, ease:'power2.out'}}, {q(0.3, fps)});",
        f"          tl.fromTo('#title-card-title', {{opacity:0, y:14}}, {{opacity:1, y:0, duration:0.45, ease:'power2.out'}}, {q(0.45, fps)});",
        f"          tl.fromTo('#title-card-rule', {{width:0}}, {{width:160, duration:0.4, ease:'power2.out'}}, {q(0.6, fps)});",
        f"          tl.to('.card-host[data-card-id=\"title-card\"]', {{opacity:0, duration:0.3, ease:'power2.in'}}, {fade_start});",
        f"          tl.set('.card-host[data-card-id=\"title-card\"]', {{visibility:'hidden'}}, {end});",
        "          ",
    ]
    return "\n".join(lines), start, end


# ---------------------------------------------------------------- captions
def build_captions(transcript_words, content_start, fps):
    words = [w for w in transcript_words if w.get("type") == "word" and w["start"] >= content_start]

    turns = []
    cur = []
    prev_speaker = None
    for w in words:
        if w.get("speaker_id") != prev_speaker and cur:
            turns.append(cur)
            cur = []
        cur.append(w)
        prev_speaker = w.get("speaker_id")
    if cur:
        turns.append(cur)

    chunks = []
    for turn in turns:
        buf = []
        for w in turn:
            buf.append(w)
            text = w["text"].strip()
            has_punct = text.endswith((".", "?", "!", ","))
            at_max = len(buf) >= MAX_WORDS_PER_CHUNK
            if (has_punct and len(buf) >= MIN_WORDS_FOR_PUNCT_BREAK) or at_max:
                chunks.append(buf)
                buf = []
        if buf:
            chunks.append(buf)

    print(f"[info] {len(words)} words -> {len(turns)} speaker turns -> {len(chunks)} caption chunks")

    hosts = []
    gsap_blocks = []
    for ci, chunk in enumerate(chunks):
        cid = f"cap-{ci:03d}"
        start = q(chunk[0]["start"], fps)
        end = q(chunk[-1]["end"] + 0.12, fps)
        duration = q(end - start, fps)

        word_spans = "".join(f'<span class="cw" id="{cid}-w{wi}">{esc(w["text"])}</span>' for wi, w in enumerate(chunk))

        card_html = f'''<div class="card" data-card-id="{cid}">
  <style>
    .card[data-card-id="{cid}"] .root {{ width:100%; height:100%; }}
    .card[data-card-id="{cid}"] .cap-row {{
      position: absolute; left: 110px; top: 90px; width: 1700px;
      display: flex; flex-wrap: wrap; justify-content: center; align-items: center;
      gap: 10px 14px;
    }}
    .card[data-card-id="{cid}"] .cw {{
      font-family: 'Inter', sans-serif; font-size: 46px; font-weight: 700;
      color: #FFFFFF; padding: 4px 12px; border-radius: 8px;
      background: transparent; text-shadow: 0 2px 10px rgba(0,0,0,0.85);
    }}
  </style>
  <div class="root">
    <div class="cap-row">{word_spans}</div>
  </div>
</div>'''

        hosts.append(
            f'''      <div class="card-host clip" data-card-id="{cid}" data-start="{start:.4f}" data-duration="{duration:.4f}" data-track-index="4" style="left:0px;top:0px;width:1920px;height:1080px;visibility:hidden;opacity:0;">
{card_html}

      </div>'''
        )

        lines = [f"          // ---- {cid} [{start}s -> {end}s] ----"]
        lines.append(f"          tl.set('.card-host[data-card-id=\"{cid}\"]', {{visibility:'visible'}}, {start});")
        lines.append(f"          tl.set('.card-host[data-card-id=\"{cid}\"]', {{opacity:1}}, {start});")
        for wi, w in enumerate(chunk):
            ws = q(w["start"], fps)
            we = q(max(w["end"], w["start"] + 1.0 / fps), fps)
            sel = f"'.card[data-card-id=\"{cid}\"] #{cid}-w{wi}'"
            lines.append(f"          tl.set({sel}, {{backgroundColor:'#4DD9C0', color:'#0F1C2B'}}, {ws});")
            lines.append(f"          tl.set({sel}, {{backgroundColor:'transparent', color:'#FFFFFF'}}, {we});")
        lines.append(f"          tl.set('.card-host[data-card-id=\"{cid}\"]', {{opacity:0, visibility:'hidden'}}, {end});")
        lines.append("          ")
        gsap_blocks.append("\n".join(lines))

    return hosts, gsap_blocks


# ---------------------------------------------------------------------- build
def build(args):
    episode_dir = Path(args.episode_dir).resolve()
    project = episode_dir / "hf-broll"
    storyboard_path = project / "storyboard.json"
    if not storyboard_path.exists():
        sys.exit(f"[error] {storyboard_path} not found — run --stage first, then author cards[]")

    storyboard = json.loads(storyboard_path.read_text())
    comp = storyboard["composition"]
    fps, W, H, dur = comp["fps"], comp["width"], comp["height"], comp["durationSeconds"]

    if not storyboard["cards"]:
        print("[warn] storyboard.json has no cards yet — building title + captions only")

    content_start = args.content_start
    if content_start is None:
        meta_path = episode_dir / "edit" / "intro_meta.json"
        if meta_path.exists():
            content_start = json.loads(meta_path.read_text())["content_start"]
            print(f"[info] using content_start={content_start} from {meta_path}")
        else:
            sys.exit("[error] --content-start not given and edit/intro_meta.json not found; "
                      "pass --content-start <seconds> explicitly (end of spoken intro + gap)")

    transcript_path = Path(args.transcript) if args.transcript else episode_dir / "edit" / "transcripts" / "combined_audio.json"
    if not transcript_path.exists():
        sys.exit(f"[error] transcript not found: {transcript_path}")
    transcript = json.loads(transcript_path.read_text())

    title = args.title
    kicker = args.title_kicker or TITLE_KICKER_TEMPLATE.format(date=args.date or episode_dir.name.split("-podcast")[0])
    title_fade_start = content_start - 0.4
    title_end = content_start - 0.1

    card_hosts, card_gsap_blocks = [], []
    for card in storyboard["cards"]:
        arch = card["archetype"]
        if arch not in BUILDERS:
            sys.exit(f"[error] unknown archetype '{arch}' in card {card['id']} — valid: {list(BUILDERS)}")
        accent = card["accentIndex"]
        cid = card["id"]
        start = q(card["startSec"], fps)
        duration = q(card["endSec"] - card["startSec"], fps)
        inner_html = BUILDERS[arch](card, accent, W, H)
        card_hosts.append(
            f'''      <div class="card-host clip" data-card-id="{cid}" data-start="{start:.4f}" data-duration="{duration:.4f}" data-track-index="2" style="left:0px;top:0px;width:{W}px;height:{H}px;visibility:hidden;opacity:0;">
{inner_html}

      </div>'''
        )
        card_gsap_blocks.append(card_gsap(card, fps))

    title_host = f'''      <div class="card-host clip" data-card-id="title-card" data-start="0.0000" data-duration="{title_end:.4f}" data-track-index="3" style="left:0px;top:0px;width:{W}px;height:{H}px;visibility:hidden;opacity:0;">
{build_title_card(title, kicker)}

      </div>'''
    title_gsap_block, _, _ = title_gsap(title_fade_start, title_end, fps)

    caption_hosts, caption_gsap_blocks = build_captions(transcript["words"], content_start, fps)

    theme_css = "\n".join(f"        --{k}: {v};" for k, v in THEME.items())

    head = f'''<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <style>
      @font-face {{ font-family: "Inter"; src: url("fonts/Inter-400-latin.woff2") format("woff2"); font-weight: 400; font-display: block; }}
      @font-face {{ font-family: "Inter"; src: url("fonts/Inter-700-latin.woff2") format("woff2"); font-weight: 700; font-display: block; }}
      @font-face {{ font-family: "SF Pro Rounded"; src: url("fonts/SFNSRounded.ttf") format("truetype"); font-weight: 400 900; font-display: block; }}
      @font-face {{ font-family: "SF Mono"; src: url("fonts/SFNSMono.ttf") format("truetype"); font-weight: 400 700; font-display: block; }}

      :root {{
{theme_css}
      }}
      * {{ box-sizing: border-box; }}
      html, body {{
        margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden;
        background: #000;
        font-family: "Inter", "SF Pro Rounded", ui-sans-serif, system-ui, sans-serif;
      }}
      #stage {{ position: relative; width: 100%; height: 100%; overflow: hidden; }}

      .video-wrapper {{
        position: absolute; left: 0; top: 0; width: {W}px; height: {H}px;
        overflow: hidden; border-radius: 0; box-shadow: none;
      }}
      .video-wrapper video {{ width: 100%; height: 100%; object-fit: cover; }}

      .card-host {{ position: absolute; pointer-events: none; overflow: hidden; }}
      .card-host .card {{ position: relative; width: 100%; height: 100%; overflow: hidden; }}
      .card-host .char {{ display: inline-block; visibility: visible; }}
      .card-host .content {{ position: relative; z-index: 1; }}
    </style>
  </head>
  <body>
    <div
      id="stage"
      data-composition-id="talking-head-recut"
      data-start="0"
      data-duration="{dur}"
      data-fps="{fps}"
      data-width="{W}"
      data-height="{H}"
    >
      <div class="video-wrapper" id="video-wrap">
        <video id="bg-video" src="input-video.mp4" muted playsinline data-start="0" data-duration="{dur}" data-track-index="1"></video>
      </div>
      <audio id="source-audio" src="input-video.mp4" data-start="0" data-duration="{dur}" data-track-index="10" data-volume="1"></audio>
'''

    tail = f'''
      <script src="vendor/gsap.min.js"></script>
      <script>
        (function () {{
          const tl = window.gsap.timeline({{ paused: true }});

{title_gsap_block}
{"".join(caption_gsap_blocks)}
{chr(10).join(card_gsap_blocks)}
          window.__timelines = window.__timelines || {{}};
          window.__timelines["talking-head-recut"] = tl;
        }})();
      </script>
    </div>
  </body>
</html>
'''

    output = head + title_host + "\n" + "\n".join(caption_hosts) + "\n" + "\n".join(card_hosts) + tail
    index_path = project / "public" / "index.html"
    index_path.write_text(output)
    print(f"[done] wrote {index_path} ({len(output)} bytes, "
          f"{len(storyboard['cards'])} B-roll cards, {len(caption_hosts)} caption chunks)")

    if args.render:
        print("[info] rendering via hyperframes...")
        subprocess.run(
            ["npx", "hyperframes", "render", "public", "--skill=talking-head-recut",
             "-o", "output.mp4", "--fps", str(fps)],
            cwd=str(project), check=True,
            env={**__import__("os").environ, "PRODUCER_BROWSER_GPU_MODE": "hardware"},
        )
        print(f"[done] rendered -> {project / 'output.mp4'}")


def main():
    parser = argparse.ArgumentParser(description="Generate a HyperFrames B-roll composition for a podcast episode")
    sub = parser.add_subparsers(dest="mode", required=True)

    stage_p = sub.add_parser("stage", help="stage assets + scaffold storyboard.json")
    stage_p.add_argument("--episode-dir", required=True)
    stage_p.add_argument("--video", required=True, help="path to final rendered episode video (absolute or relative to episode-dir)")
    stage_p.add_argument("--format", choices=list(FORMAT_PRESETS), default="landscape",
                          help="landscape (1920x1080@24, long-form podcast recuts) or "
                               "portrait (1080x1920@30, shorts/Reels/TikTok). default: landscape")
    stage_p.add_argument("--fps", type=int, default=None, help="override the format preset's fps")

    build_p = sub.add_parser("build", help="generate index.html from storyboard.json + transcript")
    build_p.add_argument("--episode-dir", required=True)
    build_p.add_argument("--title", required=True, help="title text for the intro title card")
    build_p.add_argument("--title-kicker", default=None, help='defaults to "DAILY AI PULSE · <date>"')
    build_p.add_argument("--date", default=None, help="human date for the default kicker, e.g. 'JULY 28, 2026'")
    build_p.add_argument("--content-start", type=float, default=None, help="seconds; defaults to edit/intro_meta.json's content_start")
    build_p.add_argument("--transcript", default=None, help="defaults to edit/transcripts/combined_audio.json")
    build_p.add_argument("--render", action="store_true", help="also run hyperframes render after building")

    args = parser.parse_args()
    if args.mode == "stage":
        stage(args)
    elif args.mode == "build":
        build(args)


if __name__ == "__main__":
    main()
