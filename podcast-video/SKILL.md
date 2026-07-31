---
name: podcast-video
description: Automates daily podcast video production - transcription, video rendering with waveform, chapters, and YouTube-ready subtitles
tags: [video, podcast, automation, youtube]
enabled: true
---

# Podcast Video Production Skill

Fully automated daily podcast video builder. Takes your audio file and brand video loop, outputs a publication-ready video with waveform overlay, transcript, chapter timestamps, and YouTube subtitles.

## How this fits into the daily pipeline (as of 2026-07-28)

This repo owns the *scripts* (`regenerate_dialogue.py`, `build_video.py`,
`generate_broll.py`) and is the source of truth for their exact CLI flags.
It does not own the orchestration — that lives in the Cowork
`daily-podcast-pipeline` skill, which morning-pulse now chains into
automatically every morning once the NotebookLM audio deep-dive is ready.
That skill:

1. Runs `regenerate_dialogue.py` → `build_video.py` and promotes the result
   to `<JoeBuildsSystems>/Content/<date>-podcast/daily-ai-pulse-<date>-final.mp4`
   ("Tier 1" — plain rendered episode, YouTube-uploadable as-is).
2. Runs `generate_broll.py stage` and hand-drafts `storyboard.json`, then
   **stops** — it does not run `generate_broll.py build` or the hyperframes
   render automatically. Card selection (which stat/quote/moment gets a
   card) is a judgment call Joe wants visibility into before it renders, so
   the pipeline pauses here and notifies him.
3. Only runs `generate_broll.py build` + the hyperframes render ("Tier 2")
   when Joe explicitly says "approve today's broll" / "render broll for
   &lt;date&gt;" in a later message.

See `[[JoeBuildsSystems/Projects/morning-pulse-pipeline]]` in the AgenticOS
vault for the full end-to-end architecture (morning brief → audio → this
repo → YouTube-ready folder) and the canonical `Content/<date>-podcast/`
folder contract, which daily-podcast-pipeline enforces so output doesn't
drift day to day the way it did 2026-07-25 through 2026-07-27.

## What This Skill Does

1. **Generates a spoken intro and outro** (~30s each) in your cloned ElevenLabs voice — the intro prepended (frames what's about to be discussed instead of starting cold), the outro appended (a sign-off + CTA to like/comment/subscribe so the video doesn't just cut off after the last line)
2. **Transcribes** audio (intro + episode + outro) using Scribe API (word-level timestamps)
3. **Creates boomerang loop** from your brand video
4. **Renders final video** with:
   - Seamlessly looped background
   - Synced audio waveform overlay
   - Professional visual treatment
5. **Generates YouTube assets**:
   - Chapter timestamps (auto-drafted — coarse placeholder only, see "Chapter Detection" below)
   - SRT subtitle file (word-perfect sync)
   - Upload-ready description (auto-drafted from `brief.md` if present, else a placeholder)
6. **Produces transcript** in markdown format

## Quick Start

```bash
/podcast-video
```

The skill will:
- Scan current directory for podcast audio (mp3/m4a) and brand video (mp4)
- Prompt you for episode title and any special instructions
- Run the complete production pipeline
- Output everything to `./edit/` directory

## Input Requirements

Place these files in your working directory:

1. **Audio file**: `.mp3` or `.m4a` (your podcast episode)
2. **Brand video**: `.mp4` (your logo/brand loop, ideally 5-10 seconds)
3. *(Optional)* **Episode notes**: `.md` file with show notes
4. *(Optional)* **Intro script**: `intro.txt` — a ~30s (75-90 word) spoken intro framing what the episode covers. If present, it's synthesized in your cloned voice and prepended to the episode audio automatically. Before invoking the skill, draft this from the episode's brief/notes so it's fresh per-episode rather than a fixed template — `eleven_v3` audio/emotion tags (e.g. `[curious]`, `[excited]`) are supported inline for a more expressive read. You can also pass a ready-made intro directly with `--intro-audio <mp3>` or `--intro-text-file <txt>`, or skip it entirely with `--no-intro`.
5. *(Optional)* **Outro script**: `outro.txt` — a ~20-30s spoken sign-off + CTA (thank listeners, ask for a like/comment/subscribe, tease tomorrow's episode). Same mechanism as `intro.txt`: draft it fresh per-episode before invoking the skill, synthesized in your cloned voice and appended to the end of the episode audio automatically. Without one, episodes just cut off after the last line. Override with `--outro-audio <mp3>` / `--outro-text-file <txt>`, or skip with `--no-outro`.

## Output Files

All outputs go to `./edit/`:

```
edit/
├── final.mp4                    # Upload-ready video
├── subtitles.srt                # YouTube subtitles
├── transcript.md                # Full episode transcript
├── youtube-info.md              # Chapters + description template
├── transcripts/
│   └── [audio-name].json        # Cached raw transcription
└── temp/                        # Intermediate files
    ├── boomerang.mp4
    ├── preview.mp4
    └── ...
```

## Configuration

Edit `~/.claude/skills/podcast-video/config.json`:

```json
{
  "video": {
    "trim_end_seconds": 1,
    "waveform_height": 180,
    "waveform_color": "#FFFFFF",
    "waveform_position": 490,
    "resolution": "1280x720",
    "fps": 24,
    "crf": 23
  },
  "chapters": {
    "min_chapters": 3,
    "max_chapters": 7,
    "min_gap_seconds": 120
  },
  "subtitles": {
    "max_chars_per_line": 42,
    "max_words_per_chunk": 12,
    "min_words_for_break": 5
  }
}
```

## Advanced Usage

### Specify custom files

```bash
/podcast-video --audio episode-042.mp3 --video brand-loop.mp4
```

### Skip transcription (use cached)

```bash
/podcast-video --skip-transcribe
```

### Preview mode (720p fast render)

```bash
/podcast-video --preview
```

### Custom waveform style

```bash
/podcast-video --waveform-color "#00D9FF" --waveform-height 200
```

## Requirements

- `ffmpeg` and `ffprobe` on PATH
- Python 3.8+ with packages:
  - `requests`
  - `python-dotenv`
- `ELEVENLABS_API_KEY` in environment or `.env`
- Node.js (optional, for future animation features)

## Workflow

The skill orchestrates this pipeline:

1. **Discovery**: Find audio + video files in current directory
2. **Intro/outro**: Synthesize `intro.txt`/`outro.txt` if present, assemble into one combined audio file
3. **Transcription**: Send combined audio to Scribe, cache result
4. **Video prep**: Trim black frames, create boomerang loop
5. **Render**: Composite background + waveform + audio
6. **Analysis**: Parse transcript, draft a coarse chapter placeholder (not semantic — see below)
7. **Chapters**: Write the placeholder chapter timestamps
8. **Subtitles**: Build word-synced SRT file
9. **Package**: Assemble upload info document with an auto-drafted description
10. **Mandatory manual step**: replace the placeholder chapters (and sanity-check the description) by reading `edit/transcript.md` — see "Author real chapters + description" below. Do this every time; it is not optional and does not happen automatically.

## Full Pipeline (diarized two-speaker dialogue episodes)

The daily episodes are NotebookLM-generated two-speaker dialogue audio (the raw export NotebookLM sends each morning, typically 5-15 min, ideally 5-6 min). For these, `build_video.py` is the *second half* of the pipeline — run `regenerate_dialogue.py` first to swap in ElevenLabs voices, then hand its output to `build_video.py`:

```
1. regenerate_dialogue.py --audio raw_episode.m4a \
     --out-dir edit/dialogue --output edit/final_narration.mp3
   - Transcribes the raw audio (diarized, word-level, audio events)
   - Pitch-analyzes each diarized speaker to determine male vs. female
     (speaker order varies day to day, so this can't be assumed/hardcoded)
   - Regenerates the dialogue via ElevenLabs (eleven_v3, with emotion/audio
     tags for liveliness) — Joe's cloned voice always lands on the male
     speaker, "Hope" always on the female speaker, regardless of which
     speaker NotebookLM diarized first
   - Runs the mastering chain (compression, EQ, de-ess, loudnorm)

2. Draft intro.txt (~30s framing) and outro.txt (~20-30s sign-off + CTA to
   like/comment/subscribe) from brief.md + youtube-info.md before invoking
   build_video.py — see Input Requirements above.

3. build_video.py --audio edit/final_narration.mp3 --video brand-loop.mp4
   - Synthesizes intro.txt/outro.txt in Joe's voice, prepends/appends them
   - Re-transcribes the combined (intro + narration + outro) audio —
     required, since ElevenLabs' regenerated timing no longer matches the
     original diarized transcript's timestamps
   - Renders, generates subtitles/transcript/youtube-info, and a coarse
     chapters.txt placeholder
   - Output: edit/daily-ai-pulse-{date}-final.mp4

4. Author real chapters + description (mandatory, every episode — see
   "Chapter Detection" below): read edit/transcript.md, hand-write real
   chapter titles into edit/chapters.txt and edit/youtube-info.md, and
   tighten the auto-drafted description there.

5. Generate the YouTube thumbnail (mandatory, every episode — see
   "Thumbnail" below): invoke the `jbs-adhoc-cover` skill with a
   headline/subtitle/pose inferred from the episode, save the result into
   Content/2026-MM-DD-podcast/thumbnails/. Do not hand-roll a thumbnail any
   other way (e.g. burning text over a video frame) — jbs-adhoc-cover is
   the one system of record for JBS cover art (locked reference photos,
   brand colors, Renders tracker logging).

6. B-roll pass (title card burn-in + karaoke captions + hand-picked B-roll
   cards, including an outro CTA card synced to the spoken outro) via
   generate_broll.py — see "B-Roll Pass" below.
```

For single-narrator episodes (no diarized dialogue to regenerate), skip step 1 and run `build_video.py` directly on the raw audio, same as before.

## Thumbnail

Every episode needs a YouTube thumbnail — this was silently skipped for every episode through 2026-07-29 (the `thumbnails/` folder existed in each `Content/<date>-podcast/` dir but nothing ever wrote into it). It's now step 5 above, not an afterthought.

Thumbnail generation is **not** part of `build_video.py`/`generate_broll.py` — it's handled entirely by the separate `jbs-adhoc-cover` skill (an n8n workflow that does a Gemini pose edit against Joe's locked reference photos, in the same brand colors as this skill's B-roll theme). After `build_video.py` renders the final episode:

1. Read the episode's brief.md/hook to infer `headline` (6-8 words, the curiosity-gap), optional `subtitle`, `poseDescription` (specific, e.g. "hand on chin, eyebrows raised, looking off to the side"), and `tagCategory` (`AI News` for most daily episodes).
2. Invoke the `jbs-adhoc-cover` skill with those. It POSTs to the JBS Ad Hoc Cover Generator n8n webhook and returns `{ imageUrl, filename, headline }`.
3. Download the returned image into `Content/2026-MM-DD-podcast/thumbnails/`.

This is a per-episode judgment call (which moment/expression sells the video) the same way B-roll card content is — don't try to script the headline/pose inference away.

## B-Roll Pass

Once `build_video.py` has produced the final rendered episode, `generate_broll.py` builds a HyperFrames `talking-head-recut` composition on top of it: an intro title card (burned in for the spoken intro, fading out right as the dialogue starts), speaker-isolated karaoke captions (one speaker's turn visible at a time — an interjecting speaker's words never blend with the other's; each active word gets a teal highlight box), and hand-picked B-roll cards (`topic-marker` / `stat` / `stat-warning` / `stat-dual` / `quote` / `thesis` / `outro`), all in the established "jbs-custom" JBS theme. If the episode has a spoken outro (edit/intro_meta.json's `outro_start`), place an `outro` card spanning that segment so the CTA gets an on-screen callout, not just narration. Shared fonts/vendor/logo assets live in `~/.claude/skills/podcast-video/hf-broll-assets/`.

Card *content* — which stat, quote, or topic-marker moment gets a card, and its exact wording — is still a per-episode judgment call (read the transcript/chapters/brief and pick the moments worth calling out), not something this script infers on its own.

```
1. python3 generate_broll.py stage --episode-dir Content/2026-MM-DD-podcast \
     --video edit/daily-ai-pulse-2026-MM-DD-final.mp4
   - Copies fonts/vendor/images from hf-broll-assets/ into hf-broll/public/
   - Re-encodes the source video with dense keyframes for seekable rendering
   - Writes hf-broll/storyboard.json (schemaVersion 3, cards: []) if missing

2. Hand-author storyboard.json's cards[] — same schema as
   Content/2026-07-27-podcast/hf-broll/storyboard.json and
   Content/2026-07-28-podcast/hf-broll/storyboard.json: id, archetype,
   startSec, endSec, accentIndex (0-4), zone ("video-overlay"), contentHints
   (shape depends on archetype — see the two example files above).

3. python3 generate_broll.py build --episode-dir Content/2026-MM-DD-podcast \
     --title "Episode Title Here" --date "MONTH DD, YYYY"
   - content_start (seconds — where the spoken intro ends and captions/
     dialogue begin) defaults to edit/intro_meta.json's content_start,
     written automatically by build_video.py's intro step; override with
     --content-start if it's ever wrong or missing
   - Reads edit/transcripts/combined_audio.json for caption word timing
   - Writes hf-broll/public/index.html
   - Pass --render to also invoke `hyperframes render` immediately after

4. cd Content/2026-MM-DD-podcast/hf-broll && PRODUCER_BROWSER_GPU_MODE=hardware \
     npx hyperframes render public --skill=talking-head-recut -o output.mp4 --fps 24
   (skip if you passed --render in step 3)

5. Spot-check with `npx hyperframes snapshot public --at <seconds>` at a few
   card/caption moments, then promote hf-broll/output.mp4 to the top-level
   Content/2026-MM-DD-podcast/daily-ai-pulse-{date}-final.mp4.
```

## Customization

### Brand Video Guidelines

Your brand loop should:
- Be 5-10 seconds long
- Have no black frames at the end (skill auto-trims 1 second by default)
- Work visually when reversed (boomerang effect)
- Be clean at 1280×720 or higher

### Waveform Styling

Adjust in config or via flags:
- `waveform_color`: Hex color code
- `waveform_height`: Pixel height (120-240 recommended)
- `waveform_position`: Y-position from top (490 = lower third for 720p)
- `waveform_opacity`: 0.0-1.0 (default 0.9)
- `waveform_glow`: Enable/disable glow effect

### Chapter Detection

`build_video.py`'s built-in chapter detector is a coarse stub (it drops a "Chapter N" marker every 5 minutes — a no-op on any episode under ~10 min) because real topic-shift titles need semantic judgment the script doesn't have. `youtube-info.md` flags this loudly with an "⚠ AUTO-PLACEHOLDER" banner when it fires.

**Author real chapters + description — mandatory, every episode:** after `build_video.py` finishes, read `edit/transcript.md` (and `edit/subtitles.srt` for exact timestamps) and hand-write real chapter titles into both `edit/chapters.txt` and the Chapter Timestamps block in `edit/youtube-info.md`. Also sanity-check the auto-drafted Description section there (pulled from `brief.md`) and tighten it. Skipping this step is what produced placeholder-only `youtube-info.md` files for the 2026-07-27 and 2026-07-29 episodes — don't let it happen again.

## Troubleshooting

### "No audio file found"
Place a `.mp3` or `.m4a` file in your current directory.

### "Transcription failed"
Check `ELEVENLABS_API_KEY` is set correctly. Verify API quota.

### "Waveform too dim"
Increase `waveform_opacity` to 1.0 or adjust `waveform_color` to a brighter value.

### "Chapters not accurate"
Expected — chapter detection is a coarse placeholder by design. Read `edit/transcript.md`, write real chapter titles into `edit/chapters.txt` and `edit/youtube-info.md`. This is a required step on every episode, not a fallback for when detection misfires.

### "Video/audio out of sync"
This shouldn't happen with word-level timestamps. Report as bug if it does.

## Examples

### Daily podcast automation
```bash
cd ~/podcasts/daily-pulse/2026-07-24/
# Drop in: episode.mp3, brand-loop.mp4
/podcast-video
# Outputs ready in ./edit/ — upload to YouTube
```

### Custom styling for special episode
```bash
/podcast-video \
  --waveform-color "#FF5A00" \
  --waveform-height 220 \
  --video special-brand.mp4
```

### Batch process multiple episodes
```bash
for dir in 2026-07-*/; do
  cd "$dir"
  /podcast-video --skip-interaction
  cd ..
done
```

## Performance

- **Transcription**: ~1-2 minutes for 30-minute episode (depends on API)
- **Video render**: ~3-5 minutes for 30-minute episode at 720p
- **Total runtime**: ~5-8 minutes for complete pipeline

## Future Enhancements

Planned features:
- Auto-upload to YouTube via API
- Multi-track audio mixing (e.g. a low-volume instrumental bed under the spoken intro)
- Animated lower-thirds for speaker names
- Chapter-specific B-roll overlays
- Social media clip extraction

## Support

Issues or feature requests: Create an issue in the skill repository or contact the maintainer.

## Credits

Built on the `video-use` framework. Uses:
- ElevenLabs Scribe API for transcription
- FFmpeg for video processing
- Python for orchestration

---

**Version:** 1.0.0
**Last Updated:** 2026-07-24
