# Vertical clips for TikTok / Instagram Reels (the current shorts workflow)

Every finished episode gets 3 vertical clips of 45-75 seconds, built from the episode's own
pieces. This replaces the older chapter-length, waveform-style flow in `BUILD_SHORTS.md` for the
daily episodes. Added 2026-10-02 after a prototype on the 2026-10-02 episode.

Why not crop the YouTube video: its cards and captions are burned in at 1920x1080 and get cut
off in 9:16. `generate_broll.py`'s `portrait` preset only moves card positions; its captions and
card layouts are still landscape. `portrait_clip.py` is a separate, portrait-native renderer.

## One source of truth

- **Settings:** `shorts/shorts_config.json` (canvas, clip length bounds, CTA text, asset paths).
- **Assets:** `podcast-video/hf-broll-assets/` (fonts, GSAP, brand images, the vertical
  background `images/jbs-dark-vertical.png`). Clips **link** to this folder. Nothing is copied
  per clip or per episode. Change a font or the background once, here.
- **Safe zones:** `shorts/safe_zones.json` (`cross_post_safe`: top 220, bottom 420, left 60,
  right 120). The script asserts its layout fits inside it.
- **Do not use** `~/.claude/skills/podcast-video/`: it is an old separate copy of this folder
  (last updated Sep 17) and will drift. The scripts and assets live in this repo.

## Per-episode steps

1. **Pick clips.** `python3 shorts/list_sentences.py --episode-dir <Content/DATE-podcast>`
   prints every sentence with start/end seconds and speaker. Choose 3 windows, one per
   distinct topic (the chapters in `edit/youtube-info.md` and YouTube's "Suggested clips" are good
   topic hints). Each window: 45-75s, starts on a sentence that works as a hook, ends on a sentence end.
2. **Write the spec** `<episode>/shorts/clips.json` (see `clips.example.json`). Per clip:
   `slug`, `start`, `end` (seconds in the final video), `headline` (<= 60 chars), `cards[]`.
   Card types: `stat`, `stat-dual`, `quote`, `steps`, `compare`. Put each card's `at` where the
   number or idea is spoken.
   - Use only facts that are in the final transcript and passed the claims report. Claims that
     were reworded to an attribution ("one reviewer's test") keep that attribution in the headline and cards.
   - Quotes must be word-for-word from the transcript.
3. **Validate:** `portrait_clip.py --episode-dir <ep> --validate-only` (checks sentence boundaries,
   length, headline length, card timing against the real transcript).
4. **Render:** `portrait_clip.py --episode-dir <ep>` (one at a time with `--only <slug>`).
   Output: `<episode>/shorts/<slug>/<slug>.mp4` (1080x1920, 30fps, h264 + aac). The work folder is
   deleted after each render (`--keep-work` to keep it). Run it as a tracked background task, not
   `nohup`: a child of a finished shell call is killed. About 2.5 minutes per clip.
5. **Look at it:** `--snapshots 3,24,50 --no-render` shows frames before rendering. After rendering,
   pull frames from the MP4 (`ffmpeg -ss <t> -i clip.mp4 -frames:v 1`) and check the cards, the
   caption position and the end card.
6. **Cover image** (one per clip). Put a `cover` block in each clip's spec (`platform: "tiktok"`,
   `headline` 6-8 words, `subtitle` 4-6 words, `tagCategory`, `poseDescription`) and run the
   `jbs-adhoc-cover` skill with it. The tool saves the image to Drive (TikTok Images folder) and
   sends Joe a Slack message per cover. It returns about 1076x1927 (9:16), which is fine; do not resize.
   - Pose variety: check the last few covers/thumbnails and pick a clearly different archetype per clip.
   - Identity check (mandatory): compare each cover's face to the locked reference photo (width, beard
     length/fullness, forehead height). Compound asks (head turn + big body change + narrowed eyes)
     drift; keep the head front-facing and change one thing at a time. If a cover drifts, regenerate
     once with a simpler pose; if it still drifts, ask Joe instead of looping.
   - Download each cover through the Google Drive API (`download_file_content`, base64) into
     `shorts/<slug>/<slug>-cover.jpg`. The local Drive sync copy is online-only. Download one file per
     call and match results by the returned file id: parallel downloads can overwrite each other's saved result.
   - Do NOT publish clip covers to Viewscreen: its "current cover" is the YouTube thumbnail.
7. **Description** per clip in `shorts/<slug>/<slug>-post.md`: a TikTok caption and an Instagram Reels
   caption (keyword in the first ~125 characters, 3-6 hashtags, "Full episode on YouTube (link in bio)",
   stated character counts that match), plus a `## Keywords` section. Same fact rules as the clip
   itself (claim-checked numbers, attributions kept). Leave `[PASTE YOUTUBE EPISODE LINK]` for Joe.
8. **Check everything:** `check_clip_assets.py --episode-dir <ep>` (mp4 1080x1920 with audio, cover
   9:16, post.md within limits) and `qa-episode` check 4.

Nothing here uploads or posts to TikTok/Instagram. Posting stays manual. (The cover step does send Joe a
Slack message and write to his Drive, as `jbs-adhoc-cover` always does.)

## Layout (1080x1920)

| Zone | y range | What |
|---|---|---|
| Top UI chrome (unsafe) | 0-220 | nothing |
| Headline | 230-~440 | kicker + headline, whole clip |
| Card panel | 500-1020 | one card at a time, 900px wide column |
| Captions | 1070-1500 | word-by-word, current word highlighted |
| Bottom UI chrome (unsafe) | 1500-1920 | nothing |
| End card | 1170-1490 | last 3.2s: logo + "Full episode on YouTube" |

## Tests

`python3 shorts/test_portrait_clip.py` (config/assets exist, clip-asset checker pass/fail cases, layout inside the safe zone,
caption chunking, spec validation, assets are links not copies, HTML uses the safe column).
