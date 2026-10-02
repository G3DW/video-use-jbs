#!/usr/bin/env python3
"""Tests for portrait_clip.py. Run: .venv/bin/python3 podcast-video/shorts/test_portrait_clip.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import portrait_clip as pc  # noqa: E402


def W(text, start, end, spk="speaker_0"):
    return {"text": text, "start": start, "end": end, "type": "word", "speaker_id": spk}


def sentence_words():
    # "Hello there my friend." (speaker_0) then "Yes it is a very long sentence indeed." (speaker_1)
    ws, t = [], 0.0
    for tok in "Hello there my friend.".split():
        ws.append(W(tok, t, t + 0.3)); t += 0.4
    for tok in "Yes it is a very long sentence indeed.".split():
        ws.append(W(tok, t, t + 0.3, "speaker_1")); t += 0.4
    return ws


def test_config_and_assets():
    assert pc.ASSETS.is_dir(), pc.ASSETS
    assert (pc.ASSETS / pc.BACKGROUND).is_file()
    for sub in pc.CFG["assets"]["subdirs"]:
        assert (pc.ASSETS / sub).is_dir(), sub
    assert (pc.ASSETS / "fonts" / "Inter-700-latin.woff2").is_file()


def test_layout_inside_safe_zone():
    assert pc.HEADLINE_TOP >= pc.TOP
    assert pc.CARD_TOP + pc.CARD_H <= pc.H - pc.BOTTOM
    assert pc.CAP_TOP + pc.CAP_H <= pc.H - pc.BOTTOM
    assert pc.CTA_TOP + pc.CTA_H <= pc.H - pc.BOTTOM
    assert pc.LEFT + pc.COL_W <= pc.W - pc.RIGHT


def test_caption_chunks():
    chunks = pc.caption_chunks(sentence_words())
    for c in chunks:
        assert len(c) <= pc.MAX_WORDS
        assert len({w["speaker_id"] for w in c}) == 1, "a chunk must not mix speakers"
    assert sum(len(c) for c in chunks) == 12


def test_validate_spec():
    ws = sentence_words()
    ok = {"slug": "good_one", "start": 0.0, "end": ws[3]["end"], "headline": "A short headline", "cards": []}
    errs, warns = pc.validate_spec(ok, ws)
    assert not errs, errs
    assert any("target" in w for w in warns), "a 1.5s clip should warn about length"
    mid = dict(ok, end=ws[2]["end"])
    assert any("mid-sentence" in w for w in pc.validate_spec(mid, ws)[1])
    mid_start = dict(ok, start=ws[1]["start"])
    assert any("mid-sentence" in w for w in pc.validate_spec(mid_start, ws)[1])
    assert pc.validate_spec(dict(ok, slug="bad slug!"), ws)[0]
    assert pc.validate_spec(dict(ok, cards=[{"type": "nope", "at": 0.5}]), ws)[0]
    assert pc.validate_spec(dict(ok, cards=[{"type": "stat", "at": 99.0, "value": "1", "label": "x"}]), ws)[0]
    assert pc.validate_spec({"slug": "x"}, ws)[0]
    long_headline = dict(ok, headline="x" * 61)
    assert any("headline" in w for w in pc.validate_spec(long_headline, ws)[1])


def test_stage_work_links_not_copies():
    with tempfile.TemporaryDirectory() as d:
        work = Path(d) / "work"
        # a stale COPIED folder must be replaced by a link
        (work / "public" / "fonts").mkdir(parents=True)
        (work / "public" / "fonts" / "old.txt").write_text("stale")
        public = pc.stage_work(work)
        for sub in pc.CFG["assets"]["subdirs"]:
            link = public / sub
            assert link.is_symlink(), f"{sub} should be a symlink"
            assert link.resolve() == (pc.ASSETS / sub).resolve()
        pc.stage_work(work)  # idempotent
        assert (public / "fonts").is_symlink()


def test_html_uses_safe_column_and_config():
    ws = sentence_words()
    spec = {"slug": "t", "start": 0.0, "end": ws[-1]["end"], "headline": "Sonnet 5.5 test headline",
            "cards": [{"type": "stat", "at": 0.5, "dur": 2.0, "value": "$7.60", "label": "x", "tag": "T"},
                      {"type": "stat-dual", "at": 1.0, "dur": 2.0, "valueA": "$2", "labelA": "a", "valueB": "$10", "labelB": "b"},
                      {"type": "quote", "at": 1.0, "dur": 2.0, "text": "q"},
                      {"type": "steps", "at": 1.0, "dur": 2.0, "title": "T", "steps": [{"text": "one", "at": 1.2}]},
                      {"type": "compare", "at": 1.0, "dur": 2.0, "aLabel": "A", "aDetail": "a", "bLabel": "B", "bDetail": "b"}]}
    html = pc.build_html(spec, ws, 0.0, 6.0, 9.2)
    assert f"left:{pc.LEFT}px" in html and f"width:{pc.COL_W}px" in html
    assert pc.BACKGROUND in html
    assert "Sonnet&nbsp;5.5" in html, "keep 'Sonnet 5.5' on one line"
    assert pc.CFG["text"]["cta_title"] in html
    assert "window.__timelines" in html and 'data-width="1080"' in html and 'data-height="1920"' in html
    assert "jbs-monogram" not in html, "dark monogram is invisible on the dark panels"
    big = pc.card_stat({"value": "1 fake stat", "label": "x"}, "c", 0)[0]
    assert "font-size:92px" in big, "long stat values must shrink to fit the column"


def _make_clip(root, slug, with_cover=True, caption=None):
    import subprocess
    d = root / "shorts" / slug
    d.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=1:r=30",
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "1", "-c:v", "libx264", "-c:a", "aac",
                    "-pix_fmt", "yuv420p", str(d / f"{slug}.mp4")], check=True)
    if with_cover:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=1076x1927:d=1",
                        "-frames:v", "1", str(d / f"{slug}-cover.jpg")], check=True)
    cap = caption or "Claude Sonnet 5.5 costs $2 in and $10 out per million tokens. Full episode on YouTube (link in bio). #ClaudeSonnet55 #AIPricing #AITools"
    (d / f"{slug}-post.md").write_text(
        f"# {slug}\n\n## TikTok caption ({len(cap)} chars)\n\n{cap}\n\n## Instagram Reels caption ({len(cap)} chars)\n\n{cap}\n\n## Keywords\n\nClaude Sonnet 5.5 pricing, cost per task\n")


def test_check_clip_assets():
    import subprocess
    script = str(Path(__file__).resolve().parent / "check_clip_assets.py")
    def run(root):
        return subprocess.run([sys.executable, script, "--episode-dir", str(root)], capture_output=True, text=True)
    with tempfile.TemporaryDirectory() as d:
        good = Path(d) / "good"; _make_clip(good, "ok-clip")
        r = run(good); assert r.returncode == 0, r.stdout
    with tempfile.TemporaryDirectory() as d:
        nocover = Path(d) / "a"; _make_clip(nocover, "no-cover", with_cover=False)
        r = run(nocover); assert r.returncode == 1 and "cover image missing" in r.stdout, r.stdout
    with tempfile.TemporaryDirectory() as d:
        notags = Path(d) / "b"; _make_clip(notags, "no-tags", caption="Claude Sonnet 5.5 pricing explained with no hashtags at all.")
        r = run(notags); assert r.returncode == 1 and "hashtags" in r.stdout, r.stdout
    with tempfile.TemporaryDirectory() as d:
        nokw = Path(d) / "c"; _make_clip(nokw, "no-kw", caption="Something unrelated up front. #One #Two #Three")
        r = run(nokw); assert r.returncode == 1 and "keywords" in r.stdout, r.stdout


def test_real_episode_spec_if_present():
    ep = Path("/Users/joey_makes_stuff/Documents/AgenticOS/JoeBuildsSystems/Content/2026-10-02-podcast")
    spec_path = ep / "shorts" / "clips.json"
    tr = ep / "edit" / "transcripts" / "combined_audio.json"
    if not (spec_path.exists() and tr.exists()):
        print("  (skipped: 2026-10-02 episode files not present)")
        return
    words = json.loads(tr.read_text())["words"]
    for spec in json.loads(spec_path.read_text()):
        errs, warns = pc.validate_spec(spec, words)
        assert not errs, (spec["slug"], errs)
        assert not warns, (spec["slug"], warns)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} tests passed")
