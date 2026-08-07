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

1. regenerate_dialogue.py --audio raw_episode.m4a \
     --out-dir edit/dialogue --output edit/final_narration.mp3 \
     --transcript edit/source_transcript/transcripts/<stem>.humanized.json \
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
   brand colors, Renders tracker logging).

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
- **Meta title: 60 character limit.** Front-load the primary keyword (the tool/product name) and, where the episode supports it, a high-intent comparison or modifier term people actually search (e.g. "vs Claude Code," "pricing," "review") rather than a clever-but-keyword-empty phrase. Should differ in wording from the on-page title so the two don't cannibalize the same SERP real estate.
- **Meta description: 145 character limit.** Lead with the concrete hook (the stat, the catch, the surprising mechanism), cover secondary keywords the title didn't fit, and close on an extractable answer-style clause — this is prime AEO real estate for answer-engine snippet pulls.
- Draft 2-3 candidate pairs, pick the strongest by the same CTR + keyword-match logic as "YouTube Title" above, and write the winner (plus alternates) into a `## SEO Meta` block in `blog_post_draft.md`, directly under the `**Tags:**` line — e.g.:
  ```
  ## SEO Meta (for Beehiiv SEO settings — not the page title/subtitle above)

  **Meta Title (60 char limit):** ...
  **Meta Description (145 char limit):** ...

  Alternates:
  - Title: ... (NN)
  - Description: ... (NN)
  ```
- When the post is eventually pushed live via `save_post`, pass the winning pair as `seo_settings.default_title` / `seo_settings.default_description` so the SERP metadata matches what was authored here rather than falling back to the post title/body.

**Mandatory no-ai-slop pass, with an explicit em-dash count check:** run the drafted post through `no-ai-slop` same as the title. Pattern-scanning alone isn't enough — explicitly count em dashes (`grep -o '—' <file> | wc -l`) and get it to 0-1 for a post this length. The 2026-08-06 sample draft had 30 on first pass (missed on a pattern-only scan) and needed a dedicated count-and-fix pass, converting each to whatever it was actually doing: colons for label/list intros, parentheses for true asides, periods where it was just glue holding two sentences together.

**Content tags:** call `list_content_tags` on the publication and pick 2-4 tags whose description genuinely matches the post's actual topic — not just keyword overlap. Prefer tags that name the specific mechanism/theme covered (e.g. "Prompt Engineering" for a post centered on prompt contracts) over broad umbrella tags applied to everything. Don't stretch a technique-used-to-write-the-post (e.g. GEO) into a topic tag unless the post is actually about that technique. If the existing tag set doesn't cover recurring topic clusters well, that's a signal to expand the taxonomy (a separate task, not something to solve ad hoc per-post — see the content-tags-reference task pattern).

**Images:** default to reusing the NotebookLM-slideshow images already staged for B-roll (`hf-broll-assets/images/notebooklm-slides/`, see "NotebookLM Slide Assets" below) if any are thematically relevant to the episode — zero extra generation cost. A dedicated header/secondary image pair (matching the newsletter's normal two-image pattern) is a `jbs-adhoc-cover`-style addition, not yet built into this step.

**Publishing:** draft only, via Beehiiv's `save_post` (never auto-publishes — promotion stays a manual action in the Beehiiv UI). `learn_post_authoring` (the tool that returns Beehiiv's exact HTML contract) is plan-gated on the current subscription; until upgraded, write the draft as reviewable markdown for manual copy-paste into the Beehiiv editor rather than risk pushing malformed HTML via `save_post`.

**Backfilling past episodes:** for the standing daily process, drafts live at `Content/<date>-podcast/edit/blog_post_draft.md`, next to that episode's other pipeline output. When backfilling a batch of already-published episodes instead, save all of them flat into one consolidated folder (`Content/podcast-blog-backfill/<date>-blog-post.md`) rather than spreading them across per-episode folders — easier to grab each one for manual copy-paste without navigating in and out of dated directories. Episode source folders for a backfill batch may live in a Drive archive rather than locally; if the local `CloudStorage` mount fails to read/copy a file directly (`Resource deadlock avoided` or similar), fall back to the Google Drive API (`search_files` for the file ID, `download_file_content` to fetch it, decode the returned base64 locally) rather than retrying the same local read repeatedly.

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

**Version:** 1.3.0
**Last Updated:** 2026-08-07
