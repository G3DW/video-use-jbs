#!/usr/bin/env python3
"""Render a vertical (1080x1920) short from a finished podcast episode.

The long-form B-roll pass (generate_broll.py) is laid out for 1920x1080: its
captions and cards are hard-coded to that canvas, so cropping the YouTube video
cuts them off. This script rebuilds a clip from the episode's source pieces
instead: the dubbed audio, the word timings in edit/transcripts/combined_audio.json,
the vertical brand background, and a small per-clip spec of cards.

Everything is laid out inside the cross-platform safe zone from safe_zones.json
(TikTok + Instagram/Facebook Reels UI chrome): top 220, bottom 420, left 60,
right 120 on a 1080x1920 canvas.

    portrait_clip.py --episode-dir <Content/DATE-podcast> [--spec clips.json] [--only slug]
                     [--snapshots 3,12,30] [--no-render] [--keep-work] [--validate-only]

Settings live in shorts_config.json. Assets (fonts, GSAP, background, logos) are LINKED from the
one canonical folder it names (podcast-video/hf-broll-assets), never copied into each episode or clip.
--spec defaults to <episode-dir>/shorts/clips.json. Use list_sentences.py to pick clip boundaries.

clips.json is a list of clip specs:
    {
      "slug": "cheaper-per-token",
      "start": 134.9, "end": 189.1,            # absolute seconds in the episode's final video
      "headline": "Cheaper per token is not cheaper per task",
      "cards": [
        {"type": "stat", "at": 158.2, "dur": 5.5, "value": "$7.60",
         "label": "Average cost per task (Artificial Analysis)", "tag": "MAX EFFORT"},
        {"type": "stat-dual", "at": ..., "dur": ..., "valueA": "$2", "labelA": "...", "valueB": "$10", "labelB": "..."},
        {"type": "quote", "at": ..., "dur": ..., "text": "..."},
        {"type": "steps", "at": ..., "dur": ..., "title": "THE METHOD",
         "steps": [{"text": "Pick a real finished task", "at": 366.9}, ...]},
        {"type": "compare", "at": ..., "dur": ..., "aLabel": "...", "aDetail": "...", "bLabel": "...", "bDetail": "..."}
      ]
    }

Output: <episode-dir>/shorts/<slug>/<slug>.mp4 (1080x1920, 30fps, h264 + aac). Work files
(HTML composition, render, audio cut) live in shorts/<slug>/work/ and can be deleted.
Nothing is uploaded or posted.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from generate_broll import THEME, esc, q  # noqa: E402

CFG = json.loads((HERE / "shorts_config.json").read_text())
ASSETS = (HERE / CFG["assets"]["dir"]).resolve()   # the one canonical assets folder
BACKGROUND = CFG["assets"]["background"]
W, H, FPS = CFG["canvas"]["width"], CFG["canvas"]["height"], CFG["canvas"]["fps"]
SAFE = json.loads((HERE / CFG["safe_zones"]).read_text())["cross_post_safe"]
LEFT, RIGHT, TOP, BOTTOM = SAFE["left"], SAFE["right"], SAFE["top"], SAFE["bottom"]
COL_W = W - LEFT - RIGHT  # 900

CTA_TOP, CTA_H = 1170, 320

HEADLINE_TOP = TOP + 10          # 230
CARD_TOP = 500
CARD_H = 520
CAP_TOP = 1070
CAP_H = H - BOTTOM - CAP_TOP     # 430
MAX_WORDS = 6
MIN_WORDS_PUNCT = 3
SPOKEN_TAIL = CFG["clip"]["spoken_tail"]
CTA_DUR = CFG["clip"]["cta_seconds"]
AUDIO_LEAD = CFG["clip"]["audio_lead"]
MIN_SECONDS, MAX_SECONDS = CFG["clip"]["min_seconds"], CFG["clip"]["max_seconds"]


# Layout guard: every block must sit inside the cross-platform safe zone (safe_zones.json).
assert HEADLINE_TOP >= TOP, "headline above safe zone"
assert CARD_TOP >= TOP and CARD_TOP + CARD_H <= H - BOTTOM, "card panel outside safe zone"
assert CAP_TOP >= TOP and CAP_TOP + CAP_H <= H - BOTTOM, "captions outside safe zone"
assert CTA_TOP + CTA_H <= H - BOTTOM, "CTA outside safe zone"
assert LEFT + COL_W <= W - RIGHT, "column outside safe zone"


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


# ------------------------------------------------------------------ captions
def caption_chunks(words):
    turns, cur, prev = [], [], None
    for w in words:
        if w.get("speaker_id") != prev and cur:
            turns.append(cur)
            cur = []
        cur.append(w)
        prev = w.get("speaker_id")
    if cur:
        turns.append(cur)
    chunks = []
    for turn in turns:
        buf = []
        for w in turn:
            buf.append(w)
            t = w["text"].strip()
            if (t.endswith((".", "?", "!", ",")) and len(buf) >= MIN_WORDS_PUNCT) or len(buf) >= MAX_WORDS:
                chunks.append(buf)
                buf = []
        if buf:
            chunks.append(buf)
    return chunks


def captions_html(chunks):
    hosts, gsap = [], []
    for ci, chunk in enumerate(chunks):
        cid = f"cap-{ci:03d}"
        start = q(chunk[0]["start"], FPS)
        end = q(chunk[-1]["end"] + 0.12, FPS)
        dur = q(end - start, FPS)
        spans = "".join(f'<span class="cw" id="{cid}-w{i}">{esc(w["text"])}</span>' for i, w in enumerate(chunk))
        hosts.append(f'''      <div class="card-host clip" id="{cid}-host" data-card-id="{cid}" data-start="{start:.4f}" data-duration="{dur:.4f}" data-track-index="{5 + ci % 2}" style="left:0px;top:0px;width:{W}px;height:{H}px;visibility:hidden;opacity:0;">
        <div class="cap-row">{spans}</div>
      </div>''')
        lines = [f"          // ---- {cid} [{start}s -> {end}s] ----",
                 f"          tl.set('#{cid}-host', {{visibility:'visible'}}, {start});",
                 f"          tl.set('#{cid}-host', {{opacity:1}}, {start});"]
        for i, w in enumerate(chunk):
            ws = q(w["start"], FPS)
            we = q(max(w["end"], w["start"] + 1.0 / FPS), FPS)
            lines.append(f"          tl.set('#{cid}-w{i}', {{backgroundColor:'#4DD9C0', color:'#0F1C2B'}}, {ws});")
            lines.append(f"          tl.set('#{cid}-w{i}', {{backgroundColor:'transparent', color:'#FFFFFF'}}, {we});")
        lines.append(f"          tl.set('#{cid}-host', {{opacity:0, visibility:'hidden'}}, {end});")
        gsap.append("\n".join(lines))
    return hosts, gsap


# --------------------------------------------------------------------- cards
def panel_open(cid, accent, extra_style=""):
    return (f'<div class="panel" style="left:{LEFT}px; top:{CARD_TOP}px; width:{COL_W}px; height:{CARD_H}px; '
            f'border-top-color: var(--accent-{accent}); {extra_style}">')


def card_stat(c, cid, accent):
    tag = f'<div class="tag" id="{cid}-tag">{esc(c["tag"])}</div>' if c.get("tag") else ""
    n = len(c["value"])
    vsize = 150 if n <= 6 else (118 if n <= 8 else 92)   # keep long values inside the 900px column
    html = f'''{panel_open(cid, accent)}
        <div class="stack">
          <div class="value" id="{cid}-value" style="font-size:{vsize}px;">{esc(c["value"])}</div>
          <div class="label" id="{cid}-label">{esc(c["label"])}</div>
          {tag}
        </div>
      </div>'''
    return html, ["value", "label"] + (["tag"] if tag else [])


def card_dual(c, cid, accent):
    html = f'''{panel_open(cid, accent)}
        <div class="dual">
          <div class="blk" id="{cid}-a"><div class="num numA">{esc(c["valueA"])}</div><div class="lbl">{esc(c["labelA"])}</div></div>
          <div class="vs" id="{cid}-vs">VS</div>
          <div class="blk" id="{cid}-b"><div class="num numB">{esc(c["valueB"])}</div><div class="lbl">{esc(c["labelB"])}</div></div>
        </div>
      </div>'''
    return html, ["a", "vs", "b"]


def card_quote(c, cid, accent):
    html = f'''{panel_open(cid, accent)}
        <div class="stack">
          <div class="qmark">&ldquo;</div>
          <div class="qtext" id="{cid}-text">{esc(c["text"])}</div>
        </div>
      </div>'''
    return html, ["text"]


def card_steps(c, cid, accent):
    rows = "".join(
        f'<div class="step" id="{cid}-s{i}"><div class="n">{i + 1}</div><div class="st">{esc(s["text"])}</div></div>'
        for i, s in enumerate(c["steps"]))
    html = f'''{panel_open(cid, accent)}
        <div class="stack left">
          <div class="kick" id="{cid}-kick">{esc(c.get("title", ""))}</div>
          {rows}
        </div>
      </div>'''
    return html, ["kick"]


def card_compare(c, cid, accent):
    html = f'''{panel_open(cid, accent)}
        <div class="stack left">
          <div class="cmp" id="{cid}-a"><div class="cl a">{esc(c["aLabel"])}</div><div class="cd">{esc(c["aDetail"])}</div></div>
          <div class="cvs">VS</div>
          <div class="cmp" id="{cid}-b"><div class="cl b">{esc(c["bLabel"])}</div><div class="cd">{esc(c["bDetail"])}</div></div>
        </div>
      </div>'''
    return html, ["a", "b"]


CARD_BUILDERS = {"stat": card_stat, "stat-dual": card_dual, "quote": card_quote,
                 "steps": card_steps, "compare": card_compare}


def card_html_and_gsap(c, idx, t0):
    cid = f"card-{idx + 1}"
    accent = c.get("accent", idx % 5)
    inner, parts = CARD_BUILDERS[c["type"]](c, cid, accent)
    start = q(c["at"] - t0, FPS)
    dur = c.get("dur", 5.0)
    end = q(start + dur, FPS)
    fade = q(max(start, end - 0.28), FPS)
    host = f'''      <div class="card-host clip" id="{cid}-host" data-card-id="{cid}" data-start="{start:.4f}" data-duration="{q(end - start, FPS):.4f}" data-track-index="2" style="left:0px;top:0px;width:{W}px;height:{H}px;visibility:hidden;opacity:0;">
        <div class="card">{inner}</div>
      </div>'''
    g = [f"          // ---- {cid} [{start}s -> {end}s] ----",
         f"          tl.set('#{cid}-host', {{visibility:'visible'}}, {start});",
         f"          tl.fromTo('#{cid}-host', {{opacity:0, y:24}}, {{opacity:1, y:0, duration:0.3, ease:'power2.out'}}, {start});"]
    pop = {"value": "back.out(1.6)", "a": "back.out(1.6)", "b": "back.out(1.6)"}
    for k, part in enumerate(parts):
        at = q(start + 0.12 + 0.18 * k, FPS)
        ease = pop.get(part, "power2.out")
        extra = ", scale:0.6" if part in ("value", "a", "b") and c["type"] in ("stat", "stat-dual") else ""
        reset = ", scale:1" if extra else ""
        g.append(f"          tl.fromTo('#{cid}-{part}', {{opacity:0{extra}}}, {{opacity:1{reset}, duration:0.35, ease:'{ease}'}}, {at});")
    if c["type"] == "steps":
        for i, s in enumerate(c["steps"]):
            sat = q(max(start + 0.2, s["at"] - t0 - 0.1), FPS)
            g.append(f"          tl.fromTo('#{cid}-s{i}', {{opacity:0, x:-30}}, {{opacity:1, x:0, duration:0.35, ease:'power2.out'}}, {sat});")
    g.append(f"          tl.to('#{cid}-host', {{opacity:0, duration:0.28, ease:'power2.in'}}, {fade});")
    g.append(f"          tl.set('#{cid}-host', {{visibility:'hidden'}}, {end});")
    return host, "\n".join(g)


# ------------------------------------------------------------------ document
CSS = f'''
      @font-face {{ font-family: "Inter"; src: url("fonts/Inter-400-latin.woff2") format("woff2"); font-weight: 400; font-display: block; }}
      @font-face {{ font-family: "Inter"; src: url("fonts/Inter-700-latin.woff2") format("woff2"); font-weight: 700; font-display: block; }}
      @font-face {{ font-family: "SF Pro Rounded"; src: url("fonts/SFNSRounded.ttf") format("truetype"); font-weight: 400 900; font-display: block; }}
      @font-face {{ font-family: "SF Mono"; src: url("fonts/SFNSMono.ttf") format("truetype"); font-weight: 400 700; font-display: block; }}
      :root {{ {" ".join(f"--{k}: {v};" for k, v in THEME.items())} }}
      * {{ box-sizing: border-box; }}
      html, body {{ margin:0; padding:0; width:100%; height:100%; overflow:hidden; background:#0B121B;
        font-family: "Inter", "SF Pro Rounded", ui-sans-serif, system-ui, sans-serif; }}
      #stage {{ position: relative; width:100%; height:100%; overflow:hidden; }}
      #bg {{ position:absolute; left:0; top:0; width:{W}px; height:{H}px; background:url("{BACKGROUND}") center/cover no-repeat; }}
      #veil {{ position:absolute; left:0; top:0; width:{W}px; height:{H}px; background:rgba(11,18,27,0.38); }}
      .card-host {{ position:absolute; pointer-events:none; overflow:hidden; }}
      .card-host .card {{ position:relative; width:100%; height:100%; }}

      .kicker {{ position:absolute; left:{LEFT}px; top:{HEADLINE_TOP}px; width:{COL_W}px; font-family:'SF Mono','Inter',monospace;
        font-size:26px; letter-spacing:5px; font-weight:700; color:var(--accent-0); text-transform:uppercase; }}
      .headline {{ position:absolute; left:{LEFT}px; top:{HEADLINE_TOP + 44}px; width:{COL_W}px; margin:0;
        font-family:'SF Pro Rounded','Inter',sans-serif; font-size:66px; font-weight:800; line-height:1.08; color:#FFFFFF;
        text-shadow:0 3px 16px rgba(0,0,0,0.8); }}

      .panel {{ position:absolute; background:rgba(15,28,43,0.985); border-top:3px solid var(--accent-0);
        box-shadow:0 -6px 40px rgba(77,217,192,0.18), 0 18px 50px rgba(0,0,0,0.45); padding:36px 44px;
        display:flex; align-items:center; justify-content:center; }}
      .stack {{ display:flex; flex-direction:column; align-items:center; text-align:center; width:100%; }}
      .stack.left {{ align-items:flex-start; text-align:left; }}
      .value {{ font-family:'SF Mono','Inter',monospace; font-size:150px; font-weight:700; line-height:1; color:#FFFFFF; white-space:nowrap; }}
      .label {{ font-family:'Inter',sans-serif; font-size:44px; line-height:1.25; color:var(--text-light); margin-top:22px; max-width:800px; }}
      .tag {{ font-family:'SF Mono','Inter',monospace; font-size:24px; letter-spacing:3px; font-weight:700; color:var(--accent-0);
        background:rgba(139,159,212,0.12); border:1px solid var(--accent-0); padding:9px 18px; border-radius:6px; margin-top:24px; }}
      .dual {{ display:flex; align-items:center; justify-content:center; width:100%; }}
      .blk {{ text-align:center; flex:1; }}
      .num {{ font-family:'SF Mono','Inter',monospace; font-size:130px; font-weight:700; line-height:1; }}
      .numA {{ color:var(--accent-0); }} .numB {{ color:var(--text-light); opacity:0.7; }}
      .lbl {{ font-family:'Inter',sans-serif; font-size:34px; color:var(--text-light); margin-top:16px; }}
      .vs {{ font-family:'SF Mono','Inter',monospace; font-size:32px; color:var(--text-light); opacity:0.5; margin:0 18px; }}
      .qmark {{ font-family:'SF Pro Rounded','Inter',sans-serif; font-size:130px; line-height:0.6; color:var(--accent-0); opacity:0.55; margin-bottom:18px; }}
      .qtext {{ font-family:'SF Pro Rounded','Inter',sans-serif; font-size:60px; font-weight:700; line-height:1.16; color:#FFFFFF; }}
      .kick {{ font-family:'SF Mono','Inter',monospace; font-size:26px; letter-spacing:4px; font-weight:700; color:var(--accent-0); margin-bottom:22px; }}
      .step {{ display:flex; align-items:center; margin:12px 0; }}
      .step .n {{ flex:none; width:68px; height:68px; border-radius:50%; background:var(--accent-0); color:#0F1C2B; font-family:'SF Mono','Inter',monospace;
        font-size:38px; font-weight:700; display:flex; align-items:center; justify-content:center; margin-right:26px; }}
      .step .st {{ font-family:'SF Pro Rounded','Inter',sans-serif; font-size:44px; font-weight:700; line-height:1.12; color:#FFFFFF; }}
      .cmp {{ width:100%; }}
      .cl {{ font-family:'SF Mono','Inter',monospace; font-size:46px; font-weight:700; letter-spacing:3px; margin-bottom:10px; }}
      .cl.a {{ color:var(--accent-0); }} .cl.b {{ color:var(--accent-2); }}
      .cd {{ font-family:'Inter',sans-serif; font-size:38px; line-height:1.28; color:var(--text-light); }}
      .cvs {{ font-family:'SF Mono','Inter',monospace; font-size:26px; color:var(--text-light); opacity:0.5; margin:16px 0; }}

      .cap-band {{ position:absolute; left:0; top:{CAP_TOP - 30}px; width:{W}px; height:{CAP_H + 60}px;
        background:linear-gradient(180deg, rgba(11,18,27,0) 0%, rgba(11,18,27,0.55) 18%, rgba(11,18,27,0.55) 82%, rgba(11,18,27,0) 100%); }}
      .cap-row {{ position:absolute; left:{LEFT}px; top:{CAP_TOP}px; width:{COL_W}px; height:{CAP_H}px; display:flex; flex-wrap:wrap;
        justify-content:center; align-content:center; align-items:center; gap:10px 14px; }}
      .cw {{ font-family:'Inter',sans-serif; font-size:72px; font-weight:700; color:#FFFFFF; padding:4px 14px; border-radius:10px;
        background:transparent; text-shadow:0 3px 14px rgba(0,0,0,0.9); line-height:1.12; }}

      .cta-wrap {{ position:absolute; left:{LEFT}px; top:{CTA_TOP}px; width:{COL_W}px; height:{CTA_H}px; display:flex; flex-direction:column;
        align-items:center; justify-content:center; text-align:center; background:rgba(15,28,43,0.985); border-top:3px solid var(--accent-0);
        box-shadow:0 18px 60px rgba(0,0,0,0.5); padding:30px; }}
      .cta-k {{ font-family:'SF Mono','Inter',monospace; font-size:28px; letter-spacing:5px; font-weight:700; color:var(--accent-0); margin-bottom:18px; }}
      .cta-t {{ font-family:'SF Pro Rounded','Inter',sans-serif; font-size:64px; font-weight:800; color:#FFFFFF; line-height:1.1; }}
      .cta-s {{ font-family:'Inter',sans-serif; font-size:34px; color:var(--text-light); margin-top:22px; }}
'''


def build_html(spec, words, t0, spoken_dur, total):
    chunks = caption_chunks(words)
    cap_hosts, cap_gsap = captions_html(chunks)
    cards = [card_html_and_gsap(c, i, t0) for i, c in enumerate(spec.get("cards", []))]
    hl_end = q(spoken_dur, FPS)
    cta_start = q(spoken_dur - 0.1, FPS)
    cta_dur = q(total - cta_start, FPS)
    kicker = spec.get("kicker", CFG["text"]["kicker"])
    cta_title = spec.get("cta_title", CFG["text"]["cta_title"])
    cta_sub = spec.get("cta_sub", CFG["text"]["cta_sub"])

    headline_host = f'''      <div class="card-host clip" id="hl-host" data-card-id="hl" data-start="0.0000" data-duration="{hl_end:.4f}" data-track-index="3" style="left:0px;top:0px;width:{W}px;height:{H}px;visibility:hidden;opacity:0;">
        <div class="kicker" id="hl-kicker">{esc(kicker)}</div>
        <h1 class="headline" id="hl-text">{esc(spec["headline"]).replace(" 5.5", "&nbsp;5.5")}</h1>
      </div>'''
    band_host = f'''      <div class="card-host clip" id="band-host" data-card-id="band" data-start="0.0000" data-duration="{hl_end:.4f}" data-track-index="4" style="left:0px;top:0px;width:{W}px;height:{H}px;visibility:hidden;opacity:0;">
        <div class="cap-band"></div>
      </div>'''
    cta_host = f'''      <div class="card-host clip" id="cta-host" data-card-id="cta" data-start="{cta_start:.4f}" data-duration="{cta_dur:.4f}" data-track-index="7" style="left:0px;top:0px;width:{W}px;height:{H}px;visibility:hidden;opacity:0;">
        <div class="cta-wrap">
          <div class="cta-k" id="cta-k">{esc(kicker)}</div>
          <div class="cta-t" id="cta-t">{esc(cta_title)}</div>
          <div class="cta-s" id="cta-s">{esc(cta_sub)}</div>
        </div>
      </div>'''

    gsap = [
        "          tl.set('#hl-host', {visibility:'visible'}, 0);",
        f"          tl.fromTo('#hl-host', {{opacity:0, y:-14}}, {{opacity:1, y:0, duration:0.4, ease:'power2.out'}}, 0);",
        f"          tl.to('#hl-host', {{opacity:0, duration:0.25, ease:'power2.in'}}, {q(max(0, hl_end - 0.3), FPS)});",
        f"          tl.set('#hl-host', {{visibility:'hidden'}}, {hl_end});",
        "          tl.set('#band-host', {visibility:'visible', opacity:1}, 0);",
        f"          tl.to('#band-host', {{opacity:0, duration:0.25, ease:'power2.in'}}, {q(max(0, hl_end - 0.3), FPS)});",
        f"          tl.set('#band-host', {{visibility:'hidden'}}, {hl_end});",
        f"          tl.to('#bg', {{scale:1.05, duration:{total}, ease:'none'}}, 0);",
        "".join(cap_gsap),
        "\n".join(g for _, g in cards),
        f"          tl.set('#cta-host', {{visibility:'visible'}}, {cta_start});",
        f"          tl.fromTo('#cta-host', {{opacity:0, y:24}}, {{opacity:1, y:0, duration:0.4, ease:'power2.out'}}, {cta_start});",
        f"          tl.to('#veil', {{opacity:0, duration:0.5, ease:'power2.out'}}, {cta_start});",
        f"          tl.fromTo('#cta-k', {{opacity:0}}, {{opacity:1, duration:0.3}}, {q(cta_start + 0.35, FPS)});",
        f"          tl.fromTo('#cta-t', {{opacity:0, y:14}}, {{opacity:1, y:0, duration:0.4, ease:'power2.out'}}, {q(cta_start + 0.5, FPS)});",
        f"          tl.fromTo('#cta-s', {{opacity:0}}, {{opacity:1, duration:0.3}}, {q(cta_start + 0.75, FPS)});",
    ]

    return f'''<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <style>{CSS}</style>
  </head>
  <body>
    <div id="stage" data-composition-id="talking-head-recut" data-start="0" data-duration="{total}" data-fps="{FPS}" data-width="{W}" data-height="{H}">
      <div id="bg"></div>
      <div id="veil"></div>
{headline_host}
{band_host}
{chr(10).join(cap_hosts)}
{chr(10).join(h for h, _ in cards)}
{cta_host}
      <script src="vendor/gsap.min.js"></script>
      <script>
        (function () {{
          const tl = window.gsap.timeline({{ paused: true }});
{chr(10).join(gsap)}
          window.__timelines = window.__timelines || {{}};
          window.__timelines["talking-head-recut"] = tl;
        }})();
      </script>
    </div>
  </body>
</html>
'''


# ---------------------------------------------------------------- validation
def validate_spec(spec, all_words, episode_end=None):
    """Return (errors, warnings). Errors stop the render; warnings are printed."""
    errors, warnings = [], []
    for k in ("slug", "start", "end", "headline"):
        if k not in spec:
            errors.append(f"missing '{k}'")
    if errors:
        return errors, warnings
    slug, start, end = spec["slug"], spec["start"], spec["end"]
    if not all(c.isalnum() or c in "-_" for c in slug):
        errors.append(f"slug '{slug}' must be letters, digits, - or _")
    if end <= start:
        errors.append("end must be after start")
        return errors, warnings
    length = end - start
    if not (MIN_SECONDS <= length <= MAX_SECONDS):
        warnings.append(f"clip is {length:.0f}s, outside the {MIN_SECONDS}-{MAX_SECONDS}s target")
    if len(spec["headline"]) > 60:
        warnings.append(f"headline is {len(spec['headline'])} chars (>60 wraps to 3 lines and can touch the card)")
    words = [w for w in all_words if w.get("type") == "word"]
    inside = [w for w in words if w["start"] >= start - 0.02 and w["end"] <= end + 0.05]
    if not inside:
        errors.append(f"no words between {start} and {end}")
        return errors, warnings
    first = inside[0]
    idx = words.index(first)
    if idx > 0 and not words[idx - 1]["text"].strip().endswith((".", "?", "!")):
        warnings.append(f"start {start} is mid-sentence (previous word '{words[idx-1]['text'].strip()}'); start on a sentence")
    if not inside[-1]["text"].strip().endswith((".", "?", "!")):
        warnings.append(f"end {end} is mid-sentence (last word '{inside[-1]['text'].strip()}'); end on a sentence")
    for i, c in enumerate(spec.get("cards", [])):
        if c.get("type") not in CARD_BUILDERS:
            errors.append(f"card {i + 1}: unknown type '{c.get('type')}' (valid: {list(CARD_BUILDERS)})")
            continue
        if "at" not in c:
            errors.append(f"card {i + 1}: missing 'at'")
            continue
        if not (start <= c["at"] <= end):
            errors.append(f"card {i + 1}: at={c['at']} is outside the clip {start}-{end}")
        if c["at"] + c.get("dur", 5.0) > end + 0.5:
            warnings.append(f"card {i + 1} runs past the end of the clip")
    return errors, warnings


# ---------------------------------------------------------------------- main
def stage_work(work):
    """Create the HyperFrames project dir. Assets are symlinks to the canonical folder, not copies."""
    public = work / "public"
    public.mkdir(parents=True, exist_ok=True)
    for sub in CFG["assets"]["subdirs"]:
        src = ASSETS / sub
        if not src.is_dir():
            sys.exit(f"[error] canonical asset folder missing: {src}")
        link = public / sub
        if link.is_symlink() or link.exists():
            if link.is_symlink() and link.resolve() == src.resolve():
                continue
            shutil.rmtree(link) if link.is_dir() and not link.is_symlink() else link.unlink()
        link.symlink_to(src)
    if not (ASSETS / BACKGROUND).is_file():
        sys.exit(f"[error] background not found in canonical assets: {ASSETS / BACKGROUND}")
    return public


def find_final(episode_dir):
    cands = sorted(episode_dir.glob("daily-ai-pulse-*-final.mp4"))
    if not cands:
        sys.exit(f"[error] no daily-ai-pulse-*-final.mp4 in {episode_dir}")
    return cands[0]


def make_clip(episode_dir, spec, args):
    slug = spec["slug"]
    out_dir = episode_dir / CFG["output"]["dir_name"] / slug
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    final = find_final(episode_dir)

    transcript = json.loads((episode_dir / "edit" / "transcripts" / "combined_audio.json").read_text())
    errors, warnings = validate_spec(spec, transcript["words"])
    for w in warnings:
        print(f"[warn] {slug}: {w}")
    if errors:
        sys.exit("[error] " + slug + ": " + "; ".join(errors))
    if args.validate_only:
        print(f"[ok] {slug}: spec valid")
        return None
    start, end = spec["start"], spec["end"]
    t0 = start - AUDIO_LEAD
    spoken_dur = (end - t0) + SPOKEN_TAIL
    total = spoken_dur + CTA_DUR
    words = []
    for w in transcript["words"]:
        if w.get("type") != "word" or w["start"] < start - 0.02 or w["end"] > end + 0.05:
            continue
        w2 = dict(w)
        w2["start"] = round(w["start"] - t0, 3)
        w2["end"] = round(w["end"] - t0, 3)
        words.append(w2)
    if not words:
        sys.exit(f"[error] no words found between {start} and {end}")
    print(f"[info] {slug}: {len(words)} words, spoken {spoken_dur:.1f}s + CTA {CTA_DUR}s = {total:.1f}s")

    public = stage_work(work)
    (public / "index.html").write_text(build_html(spec, words, t0, spoken_dur, round(total, 3)))
    print(f"[done] wrote {public / 'index.html'}")

    audio = work / "audio.m4a"
    fade_at = max(0, spoken_dur - 0.35)
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{spoken_dur:.3f}", "-i", str(final), "-vn",
         "-af", f"afade=t=in:st=0:d=0.04,afade=t=out:st={fade_at:.3f}:d=0.35,apad=whole_dur={total:.3f}",
         "-c:a", "aac", "-b:a", "192k", str(audio)])

    if args.snapshots:
        run(["npx", "hyperframes", "snapshot", "public", "--at", args.snapshots], cwd=str(work))
        print(f"[done] snapshots in {public / 'snapshots'}")
    if args.no_render:
        return None

    video = work / "video.mp4"
    env = {**os.environ, "PRODUCER_BROWSER_GPU_MODE": "hardware"}
    run(["npx", "hyperframes", "render", "public", "--skill=talking-head-recut", "-o", "video.mp4", "--fps", str(FPS)],
        cwd=str(work), env=env)
    out = out_dir / f"{slug}.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(out)])
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,duration",
                            "-of", "csv=p=0", str(out)], capture_output=True, text=True, check=True).stdout.strip()
    print(f"[done] {out}\n{probe}")
    if not args.keep_work:
        shutil.rmtree(work)   # fully reproducible from the spec; assets were only links
        print(f"[info] removed {work} (use --keep-work to keep it)")
    return out


def main():
    ap = argparse.ArgumentParser(description="Render vertical clips from a finished episode")
    ap.add_argument("--episode-dir", required=True)
    ap.add_argument("--spec", default=None, help="JSON list of clip specs (default: <episode-dir>/shorts/clips.json)")
    ap.add_argument("--only", default=None, help="render only this slug")
    ap.add_argument("--snapshots", default=None, help="comma-separated seconds to snapshot before rendering")
    ap.add_argument("--no-render", action="store_true", help="build HTML (+ snapshots) but skip the render")
    ap.add_argument("--keep-work", action="store_true", help="keep shorts/<slug>/work/ after rendering")
    ap.add_argument("--validate-only", action="store_true", help="check the spec against the transcript and exit")
    args = ap.parse_args()
    episode_dir = Path(args.episode_dir).resolve()
    spec_path = Path(args.spec) if args.spec else episode_dir / CFG["output"]["dir_name"] / CFG["output"]["spec_name"]
    if not spec_path.exists():
        sys.exit(f"[error] spec not found: {spec_path}")
    specs = json.loads(spec_path.read_text())
    for spec in specs:
        if args.only and spec["slug"] != args.only:
            continue
        make_clip(episode_dir, spec, args)


if __name__ == "__main__":
    main()
