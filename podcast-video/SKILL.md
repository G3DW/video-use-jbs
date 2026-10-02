---
name: podcast-video
description: Automates daily podcast video production - transcription, video rendering with waveform, chapters, and YouTube-ready subtitles
tags: [video, podcast, automation, youtube]
enabled: true
---

# Podcast Video Production Skill

Fully automated daily podcast video builder. Takes your audio file and brand video loop, outputs a publication-ready video with waveform overlay, transcript, chapter timestamps, and YouTube subtitles.

## ⚠ MANDATORY ROUTING — read this before doing anything else

**This file documents the scripts. It is NOT the orchestrator for daily NotebookLM episodes, and following its sections top-to-bottom for a daily episode will skip a required review gate.**

If the request is anything like "run today's podcast," "build the daily episode," "run the podcast pipeline," or a bare `/podcast-video` with no custom audio file supplied — **stop and invoke the `daily-podcast-pipeline` skill instead.** That skill (not this one) owns:
- the mandatory **Stage 1 (draft) → review → Stage 2 (production)** gate, with **no auto-proceed, ever** — Stage 2 (dubbing, full render, B-roll, thumbnail, blog draft) only runs after the user has explicitly reviewed `review.html`/the claims-report and said something like "approve today's podcast";
- the Command Center `podcast-review/<date>.json` state tracking;
- the live claim-verification pass on transcript stats.

Only follow this file's own steps directly (Quick Start, Full Pipeline, etc.) when:
- you're already executing a step that `daily-podcast-pipeline` explicitly told you to run (e.g. its Stage 2 instructions literally say "run build_video.py per that doc's step 2" — that's this file), or
- it's a genuine one-off/manual episode with audio the user handed you directly, outside the daily NotebookLM flow, where there's no brief/review-gate to speak of.

**This mistake already happened once** (2026-09-16): every daily episode's `Content/<date>-podcast/` folder got fully produced by running this file's scripts straight through, without ever loading `daily-podcast-pipeline` — so the review gate, the claims-report fact-check, and the Command Center status tracking were silently skipped for weeks. Every `podcast-review/<date>.json` before 2026-09-16 is stuck at `awaiting_local_run` even though the episodes shipped. Don't repeat that: for a daily episode, `daily-podcast-pipeline` is the first skill you load, not this one.

## How this fits into the daily pipeline (as of 2026-09-16)

This repo owns the *scripts* (`regenerate_dialogue.py`, `build_video.py`,
`generate_broll.py`) and is the source of truth for their exact CLI flags.
It does not own the orchestration — that lives in the `daily-podcast-pipeline`
skill, which morning-pulse now chains into automatically every morning once
the NotebookLM audio deep-dive is ready, and which a local Claude Code
session should also load explicitly for any daily-episode request routed
here (see the routing box above). That skill runs a strictly **two-stage**
workflow, not one continuous pass:

**Stage 1 (draft, always runs first, always stops):**
1. Raw transcription + humanization + live claim-verification against the
   transcript's stats (`claims-report.json`).
2. Draft the B-roll storyboard *plan* (anchor quotes + timing, not rendered
   assets yet) and generate the thumbnail options.
3. Write `review.html` (transcript + claims + storyboard plan + thumbnails)
   and set Command Center's `podcast-review/<date>.json` status to
   `pending_review`. **Stop.** No dubbing, no rendering, regardless of time
   of day or how the run was triggered.

**Stage 2 (production, only on explicit user approval):**
1. Voice-clone the dialogue, render the base video, promote it.
2. Generate the thumbnail (if not already done in Stage 1), author/remap the
   B-roll storyboard onto final timing, build/render/promote the HyperFrames
   B-roll pass, and draft the blog post.
3. Run final QA and save its PASS/FAIL record before reporting completion.

**Do not request separate approval for individual Stage 2 sub-steps** (B-roll,
the thumbnail, the blog draft) once Stage 2 has actually started — those are
mandatory output gates within an already-approved production run, and the
editorial judgment calls inside them (which stat gets a card, which pose for
the thumbnail) should be made autonomously. **The one approval that is never
skippable is the Stage 1 → Stage 2 transition itself** — that requires the
user to have actually seen `review.html` (or been told about it) and said
something that means "go," not just an ambient "run the pipeline" request.
Only stop mid-Stage-2 for a real blocker (missing source material, failed
required tool, or unavailable account) and report the episode as blocked —
never skip the Stage 1 review to avoid a blocker.

See `[[JoeBuildsSystems/Projects/morning-pulse-pipeline]]` in the AgenticOS
vault for the full end-to-end architecture (morning brief → audio → this
repo → YouTube-ready folder) and the canonical `Content/<date>-podcast/`
folder contract, which daily-podcast-pipeline enforces so output doesn't
drift day to day the way it did 2026-07-25 through 2026-07-27.

## Schedule and Local Retention (as of 2026-08-24)

**Weekends are off.** The daily pipeline runs Monday–Friday only — no full
podcast production on Saturday or Sunday. Whatever triggers the daily run
(morning-pulse chaining into the Cowork `daily-podcast-pipeline` skill, or a
manual `/podcast-video` invocation for "today") must check the episode date
first: if it falls on a Saturday or Sunday, skip production entirely and do
not report it as blocked/missed — a weekend with no episode is expected
behavior, not a gap to fill retroactively. If NotebookLM still drops a
weekend audio file into `Content/<date>-podcast/`, leave it in place
unprocessed; Monday's run should not attempt to catch up on it.

**48-hour local retention, then Drive archival.** `Content/<date>-podcast/`
folders are archived to Google Drive and removed from local disk ~48 hours
after the episode date to avoid unbounded local storage growth. Practical
implications:
- Any step that reads from a `Content/<date>-podcast/` folder should expect
  it to exist locally only for freshly-produced or very recent episodes
  (today, yesterday). For anything older, assume it's Drive-only.
- When a step needs an older episode's files (backfills, re-derived
  chapters, pulling a past thumbnail/asset for reference) and the local
  path is missing or a local `CloudStorage` mount read fails (e.g.
  `Resource deadlock avoided`), fall back to the Google Drive API
  (`search_files` for the file ID, `download_file_content` to fetch it) the
  same way the Blog Repurposing backfill flow already does — see
  "Backfilling past episodes" below — rather than treating a missing local
  folder as an error.
- Don't build tooling that assumes today's `Content/<date>-podcast/` folder
  will still be on disk 3+ days later.

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

**This Quick Start is for a one-off/manual episode only** (audio you hand it directly, outside the daily NotebookLM flow). For "run today's podcast" or any daily-episode request, load `daily-podcast-pipeline` instead — see the routing box near the top of this file.

```bash
/podcast-video
```

For a manual episode, the skill will:
- Scan current directory for podcast audio (mp3/m4a) and brand video (mp4)
- Prompt you for episode title and any special instructions
- Run the complete production pipeline in one pass (no review gate — there's
  no brief/claims-report to review for a manual episode)
- Output everything to `./edit/` directory

## Source File Auto-Discovery (Daily Pipeline)

For the daily NotebookLM-episode pipeline, don't ask where the source files are — they always live under the same vault root and are found the same way every time:

```
~/Documents/AgenticOS/JoeBuildsSystems/
```

Resolve all three inputs from there before starting the pipeline:

1. **Episode audio** — `Content/`, most recent subfolder matching `YYYY-MM-DD-podcast` (sort by the date in the folder name, not mtime). The NotebookLM raw two-speaker dialogue export is the `.mp3`/`.m4a` inside it (filename starts `niche-pulse-`). This date (`YYYY-MM-DD`) is the episode date and drives the lookups below.
   ```bash
   ls -d ~/Documents/AgenticOS/JoeBuildsSystems/Content/*-podcast | sort | tail -1
   ```
2. **Niche Pulse research note** — `Raw/` (top level, not `Raw/assets/` or `Raw/Last30Days/`), file matching `niche-pulse-*-<episode-date>.md` — filename is always `niche-pulse-<slug>-YYYY-MM-DD.md`, date suffix at the end.
   ```bash
   ls ~/Documents/AgenticOS/JoeBuildsSystems/Raw/niche-pulse-*-<episode-date>.md
   ```
3. **Last30Days sweep** — `Raw/Last30Days/`, file matching `*-raw-v3.md`. These filenames carry no date — match by the `updated: YYYY-MM-DD` field in the file's YAML frontmatter instead, not the filename or mtime. If no file's `updated` matches the episode date exactly, fall back to the one with the most recent `updated` value.
   ```bash
   grep -l "^updated: <episode-date>" ~/Documents/AgenticOS/JoeBuildsSystems/Raw/Last30Days/*-raw-v3.md
   ```

These three feed the pipeline's later steps: the episode audio is step 1's input, the niche-pulse note and Last30Days sweep are the "richer than transcript alone" sourcing for Blog Repurposing (see below). Resolve them once at the start of a daily run rather than re-deriving per step.

### The brand loop is a fixed asset, not something to discover per episode

Added 2026-09-03 after an episode accidentally rendered against an unrelated
portrait-orientation video some agents found by globbing the user's
`~/Documents` folder for a plausible-looking `.mp4`. The daily brand loop
**never changes** — it's the same 1280x720, 14s file every single day
(confirmed identical, byte-for-byte, in the Drive archive from at least
2026-08-13 through 2026-08-28) — so `build_video.py` now reads it from a
fixed, skill-owned path instead of searching for it:

```
~/.claude/skills/podcast-video/brand-assets/brand-loop.mp4
```

Do not search the filesystem for a brand video, do not glob the working
directory, and do not guess from a filename that "sounds right." If that
path is missing, `build_video.py` now hard-fails with an explicit error
instead of silently substituting something else — stop and ask Joe where
the current file is (or restore it from the Drive archive) rather than
picking a replacement yourself. `--video <path>` still works as an explicit
override for a genuine one-off special episode (see the "Custom styling for
special episode" example below), but that's the only sanctioned way this
ever changes.

## Input Requirements

Place these files in your working directory:

1. **Audio file**: `.mp3` or `.m4a` (your podcast episode)
2. *(Fixed asset, not per-episode)* **Brand video**: resolved automatically from `~/.claude/skills/podcast-video/brand-assets/brand-loop.mp4` — see above. Only pass `--video` if you're deliberately overriding it for a one-off episode.
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
0. (added 2026-08-04) humanize_transcript.py --transcript edit/source_transcript/transcripts/<stem>.json \
     --output edit/source_transcript/transcripts/<stem>.humanized.json \
     --report edit/source_transcript/transcripts/<stem>.humanize-report.json \
     --date <YYYY-MM-DD>
   - NotebookLM's raw two-speaker dialogue reuses the same handful of
     connective-tissue phrases nearly verbatim every episode ("let's unpack
     this", "which brings us to", "so what does this all mean", "something
     to mull over", "you, the solo creator or small business owner") — this
     becomes obvious once you binge more than a couple episodes back to
     back. This script regex-matches those specific phrases against the raw
     Scribe transcript's word list and swaps each one for a rotating
     alternative drawn from humanizer_phrases.json, tracked in
     humanizer_state.json so nothing repeats for at least 4 picks. It never
     touches analogies, stats, quotes, or anything topic-specific — those
     already vary naturally and are exactly what gets fact-checked before
     dubbing, so this pass has no way to introduce a factual error.
   - Stage 1 of the daily-podcast-pipeline skill runs this right after its
     own raw transcription (before storyboard drafting), and surfaces the
     humanize-report.json swaps in review.html so Joe sees exactly what
     changed in the same pass he already reviews for accuracy. The
     humanized transcript, not the raw one, is what storyboard-plan.json's
     anchorQuote fields should reference from that point on.

0.5. (added 2026-09-01) fix_transcript_artifacts.py --transcript edit/source_transcript/transcripts/<stem>.humanized.json \
     --output edit/source_transcript/transcripts/<stem>.humanized.artifact-fixed.json \
     --report edit/source_transcript/transcripts/<stem>.artifact-fix-report.json
   - Scribe reliably mishears a handful of technical terms/idioms in
     NotebookLM's raw audio (SQL -> "Squill", CAPTCHA -> "KPTCA"/"KPTCAs",
     "24/7" -> "two and four-seven"). Since Stage 0's transcript text IS
     the script regenerate_dialogue.py hands to ElevenLabs, an uncorrected
     mishearing doesn't just show up in captions — it gets spoken out loud
     in the redub. Run this right after humanize_transcript.py and before
     regenerate_dialogue.py so the corrected text is what actually gets
     dubbed. Deterministic dictionary-based fixes only (WORD_ARTIFACTS /
     PHRASE_ARTIFACTS in the script) — never fuzzy-match or guess, since a
     wrong guess here becomes a wrong word spoken in the final audio.
     Extend the dictionaries as new mishearings turn up in review.
   - This same script can also be re-run against the SECOND transcription
     pass (edit/transcripts/combined_audio.json, produced by step 3 below)
     if that independent ASR run mishears something the first pass got
     right (e.g. correctly-spoken "Claude" heard back as "Claw"). At that
     point it's a caption-only correction — safe to run post-hoc, since
     nothing feeds back into audio once the video's already rendered.

1. regenerate_dialogue.py --audio raw_episode.m4a \
     --out-dir edit/dialogue --output edit/final_narration.mp3 \
     --transcript edit/source_transcript/transcripts/<stem>.humanized.artifact-fixed.json \
     --speaker-map edit/speaker_map.json
   - `--transcript`/`--speaker-map` are optional (added 2026-08-04) — pass
     Stage 1's already-produced (humanized) transcript and speaker map here
     to skip the redundant re-transcription this script used to always do
     internally. Without them, falls back to the original behavior:
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
   build_video.py — see Input Requirements above. These are hand-authored
   fresh each episode (not sourced from NotebookLM's dialogue, so
   humanize_transcript.py can't touch them), but in practice they've
   converged on the same skeleton every time too — "Let's get into it." to
   close the intro, "drop a like, comment X, and subscribe so you don't
   miss tomorrow's episode. See you next time." to close the outro. Pull
   both from the rotation instead of freehanding them:
   ```
   pick_scaffold_phrase.py --category opening_energizer
   pick_scaffold_phrase.py --category cta_outro --ask "comment which X you're trying first"
   ```
   Drop the returned line in place of the old boilerplate close. Same
   humanizer_phrases.json / humanizer_state.json as step 0, so the
   no-repeat window is shared across the whole episode.

3. build_video.py --audio edit/final_narration.mp3 --video brand-loop.mp4
   - Synthesizes intro.txt/outro.txt in Joe's voice, prepends/appends them
   - Re-transcribes the combined (intro + narration + outro) audio —
     required, since ElevenLabs' regenerated timing no longer matches the
     original diarized transcript's timestamps
   - Renders, generates subtitles/transcript/youtube-info, and a coarse
     chapters.txt placeholder
   - Output: edit/daily-ai-pulse-{date}-final.mp4

3.5. (added 2026-09-01) normalize_caption_numbers.py --transcript edit/transcripts/combined_audio.json \
     --output edit/transcripts/combined_audio.captions-final.json \
     --report edit/transcripts/caption-normalize-report.json
   - Display-only pass, the mirror image of step 0.5: correctly-spoken
     dates, version numbers, and a couple of spoken-idiom numbers get
     transcribed by Scribe as words ("August thirty-first, twenty
     twenty-six", "two point o") because that's genuinely how they sound
     out loud — nothing wrong with the audio, it just reads better as
     digits on screen ("August 31, 2026", "2.0"). Never feed the output
     back into TTS; some models mispronounce a raw digit date/version
     string, so spoken audio stays as words on purpose.
   - Run fix_transcript_artifacts.py first if step 0.5's note above found
     anything in this same transcript, then this script, then regenerate
     subtitles.srt/transcript.md/chapters.txt from the corrected file
     (either build_video.py's PodcastVideoBuilder.generate_subtitles() /
     generate_transcript_markdown() / generate_chapters() called directly
     against the corrected json, or overwrite
     edit/transcripts/combined_audio.json and re-run build_video.py
     --skip-transcribe — the latter also re-renders the video, so prefer
     calling the generator methods directly when only captions changed).

4. Author real chapters + description (mandatory, every episode — see
   "Chapter Detection" below): read edit/transcript.md, hand-write real
   chapter titles into edit/chapters.txt and edit/youtube-info.md, and
   tighten the auto-drafted description there. Generate the actual YouTube
   title as its own sub-step — see "YouTube Title" below — rather than
   reusing the episode brief's headline as-is.

5. Generate the YouTube thumbnail (mandatory, every episode — see
   "Thumbnail" below): invoke the `jbs-adhoc-cover` skill with a
   headline/subtitle/pose inferred from the episode, save the result into
   Content/2026-MM-DD-podcast/thumbnails/. Do not hand-roll a thumbnail any
   other way (e.g. burning text over a video frame) — jbs-adhoc-cover is
   the one system of record for JBS cover art (locked reference photos,
   brand colors, Renders tracker logging). Choose the headline/subtitle/pose
   autonomously; do not pause for approval.

6. B-roll pass (title card burn-in + karaoke captions + hand-picked B-roll
   cards, including an outro CTA card synced to the spoken outro) via
   generate_broll.py — see "B-Roll Pass" below.

7. Blog repurposing (mandatory, every episode — see "Blog Repurposing
   (Beehiiv)" below): draft a companion blog post from transcript.md +
   brief.md + the underlying Raw/niche-pulse research note, generate a
   dedicated SEO meta title/description (see "SEO Meta" within that
   section), run it through no-ai-slop (including an explicit em-dash
   count check), pick 2-4 content tags, and save it as a Beehiiv draft (or
   reviewable markdown, until the plan supports learn_post_authoring) —
   never auto-published.

8. Draft the pinned YouTube comment (mandatory, every episode — see
   "Pinned Comment" below): a short comment pointing viewers to the
   companion blog post, written into `edit/youtube-info.md` with a
   `[PASTE YOUTUBE VIDEO COMMENT LINK... ]`-style placeholder for the
   Beehiiv post URL until that post is actually published.

9. Vertical shorts (mandatory from 2026-10-02): 3 clips of 45-75s for TikTok/Instagram,
   built with `shorts/portrait_clip.py` from the finished episode. Pick the clips with
   `shorts/list_sentences.py`, write `Content/<date>-podcast/shorts/clips.json`, validate, render.
   Assets come from one shared folder (`hf-broll-assets/`) and are linked, never copied. Full workflow:
   `shorts/PORTRAIT_CLIPS.md`. Staged only; never posted.

10. Run the `qa-episode` skill and save its PASS/FAIL table to
   `logs/qa-episode-YYYY-MM-DD.log`. Do not call the episode complete until
   every mandatory output and QA check passes (this includes the shorts).
```

For single-narrator episodes (no diarized dialogue to regenerate), skip step 1 and run `build_video.py` directly on the raw audio, same as before.

## Thumbnail

Every episode needs a YouTube thumbnail — this was silently skipped for every episode through 2026-07-29 (the `thumbnails/` folder existed in each `Content/<date>-podcast/` dir but nothing ever wrote into it). It's now step 5 above, not an afterthought.

Thumbnail generation is **not** part of `build_video.py`/`generate_broll.py` — it's handled entirely by the separate `jbs-adhoc-cover` skill (an n8n workflow that does a Gemini pose edit against Joe's locked reference photos, in the same brand colors as this skill's B-roll theme). After `build_video.py` renders the final episode:

1. Read the episode's brief.md/hook to infer `headline` (6-8 words, the curiosity-gap), optional `subtitle`, `poseDescription` (specific, e.g. "hand on chin, eyebrows raised, looking off to the side"), and `tagCategory` (`AI News` for most daily episodes).
2. Invoke the `jbs-adhoc-cover` skill with those. It POSTs to the JBS Ad Hoc Cover Generator n8n webhook and returns `{ imageUrl, filename, headline }`.
3. Download the returned image into `Content/2026-MM-DD-podcast/thumbnails/`.
4. Immediately publish the saved image to Command Center's Viewscreen feed:
   ```bash
   python3 <video-use>/podcast-video/publish_viewscreen_asset.py \
     --file Content/2026-MM-DD-podcast/thumbnails/<generated-cover> \
     --type cover --title "<episode title>" --agent DAX \
     --caption "YouTube thumbnail" --episode-date YYYY-MM-DD
   ```
   This is mandatory. The Viewscreen auto-shows the newest creative asset;
   the same feed also accepts slideshow frames and chart exports. Do not wait
   for a separate dashboard step or user approval.

This is a per-episode judgment call (which moment/expression sells the video)
the same way B-roll card content is — make it autonomously from the episode
materials. Do not ask for a separate thumbnail approval.

## B-Roll Pass

Once `build_video.py` has produced the final rendered episode, `generate_broll.py` builds a HyperFrames `talking-head-recut` composition on top of it: an intro title card (burned in for the spoken intro, fading out right as the dialogue starts), speaker-isolated karaoke captions (one speaker's turn visible at a time — an interjecting speaker's words never blend with the other's; each active word gets a teal highlight box), and hand-picked B-roll cards (`topic-marker` / `stat` / `stat-warning` / `stat-dual` / `quote` / `thesis` / `outro`), all in the established "jbs-custom" JBS theme. If the episode has a spoken outro (edit/intro_meta.json's `outro_start`), place an `outro` card spanning that segment so the CTA gets an on-screen callout, not just narration. Shared fonts/vendor/logo assets live in `~/.claude/skills/podcast-video/hf-broll-assets/`.

Card *content* — which stat, quote, or topic-marker moment gets a card, and its exact wording — is still a per-episode judgment call (read the transcript/chapters/brief and pick the moments worth calling out), not something this script infers on its own.

**Front-load the anchor metric (added 2026-09-04).** If `brief.json`'s
`trend.anchorMetric` is populated, the first non-topic-marker card should
present that exact number within the episode's first 30-45 seconds
(excluding the spoken intro), as a `stat` or `stat-warning` card — not
saved for a later moment. Front-loading the numeric hook is the clearest
performance driver found in the 2026-09-04 audit review; don't bury it
mid-episode waiting for a "better" spot.

```
1. python3 generate_broll.py stage --episode-dir Content/2026-MM-DD-podcast \
     --video edit/daily-ai-pulse-2026-MM-DD-final.mp4
   - Copies fonts/vendor/images from hf-broll-assets/ into hf-broll/public/
   - Re-encodes the source video with dense keyframes for seekable rendering
   - Writes hf-broll/storyboard.json (schemaVersion 3, cards: []) if missing

2. Autonomously author storyboard.json's cards[] from the transcript, chapters,
   and brief — do not ask for B-roll approval. Use the same schema as
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
   - Pass --render to also invoke `hyperframes render` immediately after.
     This also auto-launches a `hyperframes preview` Studio server in the
     background (log at hf-broll/preview.log) right before the render
     starts, so Joe can watch the composition timeline at
     http://localhost:3002 while the batch render runs — it's a live
     preview of the authored composition, not a progress bar on the render
     job itself. Pass --no-preview to skip this.

4. cd Content/2026-MM-DD-podcast/hf-broll && PRODUCER_BROWSER_GPU_MODE=hardware \
     npx hyperframes render public --skill=talking-head-recut -o output.mp4 --fps 24
   (skip if you passed --render in step 3 — if running this standalone
   instead, first launch `npx hyperframes preview public &` for the same
   live-preview visibility)

5. Run `npx hyperframes check public`, spot-check with
   `npx hyperframes snapshot public --at <seconds>` at title, card, caption,
   and outro moments, then run `generate_broll.py finalize` to promote the
   rendered composition to the top-level final. Do not defer this pass.
```

## Production Completion Gate

Before reporting an episode complete, verify all of the following exist and
are substantive:

- `daily-ai-pulse-YYYY-MM-DD-final.mp4` — B-roll-promoted final, with video
  and audio streams.
- `thumbnails/<generated-cover>` — created through `jbs-adhoc-cover`.
- Command Center's `data/viewscreen-assets.json` contains the generated cover
  as the current `cover` asset.
- `hf-broll/storyboard.json` and `hf-broll/public/index.html` — retained
  source for the rendered B-roll pass.
- `edit/blog_post_draft.md` — complete reviewable Beehiiv draft, including
  subtitle, tags, and SEO meta block.
- `edit/youtube-info.md` contains a `## Pinned Comment` block (drafted
  comment + alternates) — see "Pinned Comment" below.
- `logs/qa-episode-YYYY-MM-DD.log` — captured final QA PASS/FAIL table.
- `edit/source_transcript/transcripts/<stem>.claims-report.json` (added
  2026-09-04, produced by daily-podcast-pipeline Stage 1's claim-verifier
  step) — no unresolved `mismatch` or `unverifiable` entries, or an
  explicit note in the episode summary that Joe reviewed and accepted the
  risk on a specific flagged claim.

There is no default "fast episode" mode. Skipping any gate requires an
explicit user instruction and must be reported as an intentional exception.

## Blog Repurposing (Beehiiv)

Added 2026-08-06. Every episode also gets repurposed into a blog post on the Joe Builds Systems Beehiiv publication (`pub_f4c98a61-5759-4f40-bad0-7e8293cfbf58`, joebuildsai.com) — mandatory, daily cadence, not an occasional/curated thing. It is not a transcript dump: the video is the 6-8 minute distillation, the blog post is the expanded companion, written to also perform well in AI-crawler/answer-engine retrieval (GEO), not just traditional SEO.

**Source material** (richer than the video alone, so the post earns its length instead of padding a thin transcript):
- `edit/transcript.md` + `brief.md` — throughline/thesis
- The underlying `Raw/niche-pulse-*.md` research note — has the "what the wider internet's saying" section with named creators/platforms/quotes that never made the video
- The `Raw/Last30Days/*-raw-v3.md` full sweep — long-tail stats/examples/quotes for depth

**Structure:**
1. Direct-answer opening paragraph — answers "what is this about" extractably in the first 2-3 sentences (this is what both AI Overviews and LLM crawlers lift as the citable summary)
2. H2 sections mirroring the episode's chapters, each expanded with a named, attributed specific pulled from the raw sweep (creator handle, platform, exact stat) rather than generic paraphrase — GEO rewards original synthesis with attributable specifics over rehashed summary
3. Closing FAQ block, 3-4 Q&As, each a self-contained extractable answer — doubles for People Also Ask (SEO) and direct-retrieval snippets (GEO)
4. A subtitle line (SEO/GEO-carrying, distinct from the title — covers keywords the title doesn't) for Beehiiv's subtitle field, written inline in the markdown right under the H1 as `**Subtitle:** ...` so it's visible with the post copy, not just mentioned separately in chat
5. A `**Tags:** tag one, tag two, tag three` line directly under the subtitle, same reasoning — the tag picks need to travel with the post file, not live only in the conversation, so whoever's pasting into Beehiiv can grab title/subtitle/tags/body from one file without cross-referencing anything else
6. Companion-episode line linking back to the YouTube video — **the real link can't be filled in until after upload**, since this step runs before that in the pipeline (not an issue for backfills, where the video's already live and the real URL should be looked up, e.g. via the `youtube-search` skill, rather than left as a placeholder); leave an explicit `[PASTE YOUTUBE LINK HERE ONCE UPLOADED]` placeholder only when the episode genuinely hasn't published yet
7. Closing CTA links to `joebuildsai.com` (the main site), not `weekly.joebuildsai.com` — linking a newsletter-hosted post back to its own newsletter signup is circular

**Title:** reuse the same hook-generation process as the YouTube title (see "YouTube Title" above) — same winning title on both, since it's already been optimized for CTR + SEO and duplicating it here reinforces the same search term instead of splitting it. This is the page H1/on-page title, not the meta title (see "SEO Meta" immediately below) — the two serve different jobs and should say different things.

**SEO Meta** (added 2026-08-07, mandatory every post): generate a dedicated meta title and meta description for Beehiiv's SEO settings, distinct from the on-page H1/subtitle above — the H1 is what a reader sees on the page, the meta title/description are what Google's SERP and AI-crawler snippets actually show, and they have their own character budgets and framing needs.
- **Meta title: 50-69 characters inclusive.** Count every visible character, including spaces and punctuation, but not the Markdown label. Front-load the primary keyword (the tool/product name) and, where the episode supports it, a high-intent comparison or modifier term people actually search (e.g. "vs Claude Code," "pricing," "review") rather than a clever-but-keyword-empty phrase. It must differ in wording from the on-page title so the two don't cannibalize the same SERP real estate.
- **Meta description: 130-160 characters inclusive.** Count every visible character, including spaces and punctuation, but not the Markdown label. Lead with the concrete hook (the stat, the catch, the surprising mechanism), cover secondary keywords the title didn't fit, and close on an extractable answer-style clause — this is prime AEO real estate for answer-engine snippet pulls.
- Draft 2-3 candidate pairs that each already meet both character ranges, count every candidate, pick the strongest by the same CTR + keyword-match logic as "YouTube Title" above, and write the winner (plus alternates) into a `## SEO Meta` block in `blog_post_draft.md`, directly under the `**Tags:**` line — e.g.:
  ```
  ## SEO Meta (for Beehiiv SEO settings — not the page title/subtitle above)

  **Meta Title (50-69 chars; actual: NN):** ...
  **Meta Description (130-160 chars; actual: NN):** ...

  Alternates:
  - Title: ... (NN chars)
  - Description: ... (NN chars)
  ```
- When the post is eventually pushed live via `save_post`, pass the winning pair as `seo_settings.default_title` / `seo_settings.default_description` so the SERP metadata matches what was authored here rather than falling back to the post title/body.

**Mandatory no-ai-slop pass, with an explicit em-dash count check:** run the drafted post through `no-ai-slop` same as the title. Pattern-scanning alone isn't enough — explicitly count em dashes (`grep -o '—' <file> | wc -l`) and get it to 0-1 for a post this length. The 2026-08-06 sample draft had 30 on first pass (missed on a pattern-only scan) and needed a dedicated count-and-fix pass, converting each to whatever it was actually doing: colons for label/list intros, parentheses for true asides, periods where it was just glue holding two sentences together.

**Content tags:** call `list_content_tags` on the publication and pick 2-4 tags whose description genuinely matches the post's actual topic — not just keyword overlap. Prefer tags that name the specific mechanism/theme covered (e.g. "Prompt Engineering" for a post centered on prompt contracts) over broad umbrella tags applied to everything. Don't stretch a technique-used-to-write-the-post (e.g. GEO) into a topic tag unless the post is actually about that technique. If the existing tag set doesn't cover recurring topic clusters well, that's a signal to expand the taxonomy (a separate task, not something to solve ad hoc per-post — see the content-tags-reference task pattern).

**Images:** default to reusing the NotebookLM-slideshow images already staged for B-roll (`hf-broll-assets/images/notebooklm-slides/`, see "NotebookLM Slide Assets" below) if any are thematically relevant to the episode — zero extra generation cost. A dedicated header/secondary image pair (matching the newsletter's normal two-image pattern) is a `jbs-adhoc-cover`-style addition, not yet built into this step.

**Publishing:** draft only, via Beehiiv's `save_post` (never auto-publishes — promotion stays a manual action in the Beehiiv UI). `learn_post_authoring` (the tool that returns Beehiiv's exact HTML contract) is plan-gated on the current subscription; until upgraded, write the draft as reviewable markdown for manual copy-paste into the Beehiiv editor rather than risk pushing malformed HTML via `save_post`.

**Backfilling past episodes:** for the standing daily process, drafts live at `Content/<date>-podcast/edit/blog_post_draft.md`, next to that episode's other pipeline output. When backfilling a batch of already-published episodes instead, save all of them flat into one consolidated folder (`Content/podcast-blog-backfill/<date>-blog-post.md`) rather than spreading them across per-episode folders — easier to grab each one for manual copy-paste without navigating in and out of dated directories. Episode source folders for a backfill batch may live in a Drive archive rather than locally; if the local `CloudStorage` mount fails to read/copy a file directly (`Resource deadlock avoided` or similar), fall back to the Google Drive API (`search_files` for the file ID, `download_file_content` to fetch it, decode the returned base64 locally) rather than retrying the same local read repeatedly.

## Pinned Comment

Added 2026-08-26. After the video uploads and the companion blog post publishes, Joe manually pins a YouTube comment pointing viewers to the newsletter post — this is a standing habit, not a one-off, so drafting it is now a mandatory pipeline step rather than something written from scratch after the fact each day.

**Write, don't just link.** A bare "check the link below" performs worse than a comment that gives a *reason* to click — a specific detail from that day's blog post (a stat, a named source, a thing that didn't make the video) creates its own curiosity gap, the same logic as the video title and B-roll card picks.

1. Pull one concrete, specific detail from `edit/blog_post_draft.md` that isn't already the headline of the video — a named creator/source, a stat, or the sharpest sub-point from an H2 section. This is the differentiator that makes the comment worth clicking, not filler.
2. Draft 2-3 candidate comments (60-150 characters is typical for a pinned comment — short enough to read in the collapsed view). Vary the angle: direct/utility, curiosity/incomplete-loop, value-stacked. Run candidates through `no-ai-slop`.
3. Pick the strongest one autonomously (same CTR-judgment logic as YouTube Title) and write it into `edit/youtube-info.md` under a `## Pinned Comment` heading, e.g.:
   ```
   ## Pinned Comment (post after upload, then pin it)

   [chosen comment text] [PASTE BEEHIIV POST LINK HERE ONCE PUBLISHED]

   Alternates:
   - ...
   - ...
   ```
4. The Beehiiv post URL isn't known yet at this point in the pipeline (blog repurposing drafts before either the video or the post is live) — leave the explicit placeholder rather than guessing a URL. This is a manual step for Joe: post the comment on the live video, then pin it, once both the video and the blog post are actually up.

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

### YouTube Title

The `**Episode:**` title (added 2026-08-06) is not the episode brief's headline pasted in as-is, and it is not the thumbnail's on-image headline reused verbatim — thumbnail text and video title do different jobs (thumbnail wins the visual scan, title wins the search/click decision) and repeating one as the other wastes an impression. Generate it as its own sub-step, mandatory every episode:

1. Draft 4-6 hook-style title candidates by invoking the `tiktok-script-structurer` skill for its hook-type taxonomy only (Statistic, Problem, Contrarian, Curiosity Gap, Insider, Future Pacing, etc.) — not the full TikTok script structure (no on-screen text cue, visual hook, second beat). Pull the concrete stat/quote/mechanism for each hook straight from the episode's transcript/chapters, the same way B-roll card content gets picked. Explicitly exclude any candidate that duplicates the thumbnail headline's wording — they need to say different things.

   **If `brief.json`'s `trend.anchorMetric` is populated, treat it as the primary numeric hook** (added 2026-09-04, after an unsolicited YouTube-channel audit's core claim held up under a real look at the channel's own numbers: the accounting-automation episode, "This AI Accounting Tool Auto-Books 95% of Your Transactions," pulled 406 views against a typical 5-90 view range — the clearest performance signal found on the channel to date). Anchor at least one candidate directly on that figure before drafting others from scratch elsewhere in the transcript.
2. Run the candidates through `no-ai-slop` to cut AI-cadence patterns (binary contrasts, dramatic fragmentation, colon reveals) and tighten to 50-70 characters — YouTube titles run as plain text in search results with no thumbnail alongside, so they have to stand alone.
3. **Pick the best one autonomously** — don't ask the user to choose. Weigh it on two axes: click-through likelihood (a concrete stat or named entity beats an abstract claim; loss-aversion/curiosity-gap framing beats a flat description) and SEO (does it contain the actual search terms someone would type — "Claude," the specific tool/technique name, the concrete numbers — rather than only clever phrasing). A title that's punchy but keyword-empty loses to one that's slightly plainer and matches real search queries. State the pick and a one-line reason in the summary; keep the runner-up options in `youtube-info.md`'s "Alternative Titles for the algo" block for future A/B testing, same as today.
4. Write the winner into both the `**Episode:**` field and the description body's title line in `edit/youtube-info.md`.

This process was established 2026-08-06 after generating title options manually for that episode and confirming with Joe which one to lead with; going forward the pick is automatic, not a per-episode question.

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
# Drop in: episode.mp3 — the brand loop resolves automatically from
# ~/.claude/skills/podcast-video/brand-assets/brand-loop.mp4, no need to place it
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

**Version:** 1.7.0
**Last Updated:** 2026-09-17
