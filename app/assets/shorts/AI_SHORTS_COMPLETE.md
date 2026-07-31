# AI-Generated Visual Shorts - Complete System

## What This Does

Converts podcast chapters into **visually stunning AI-generated short-form videos** with:
- **AI-generated imagery** for each scene (Flux, Imagen, Recraft, etc.)
- **Smooth image-to-video animations**
- **AI-synthesized voiceover** from Blotato's ElevenLabs voices, or the
  **original podcast audio** swapped back in via `swap_audio.py`
- **Professional cinematic quality**
- **9:16 vertical format** ready for TikTok, Reels, Shorts

## How It Works

### 1. Intelligent Scene Segmentation
```
Transcript → 5-13 second semantic chunks → up to 20 scenes per chapter
```
The system analyzes your transcript and breaks it into optimal scenes based on:
- Natural sentence boundaries
- Pauses in speech
- Semantic coherence
- Optimal visual pacing (5-8s per scene, before any merging)

Blotato's template hard-caps scenes at **20**. If segmentation initially
produces more than 20 (common for chapters over ~2 minutes), the shortest
adjacent scenes are merged together until the count fits — no part of the
chapter is silently dropped.

### 2. Visual Prompt Generation
```
Scene narration → written per-scene → detailed image prompts
```
`prepare_scenes.py` writes a `scenes.json` with an empty `visual_prompt` per
scene. Those prompts are then filled in (by Claude Code in-session, or by
you by hand) so each one:
- Matches the concept being discussed
- Follows your chosen aesthetic style
- Works well for animation
- Creates visual continuity

This step makes **no network call and costs nothing** — it's a plain
Python/JSON step, not an LLM API call.

### 3. Blotato AI Generation
```
Visual prompts → Blotato API → AI images → Animated videos → Final composite
```
Blotato handles the heavy lifting:
- Generates high-quality AI images (Flux 1.1 Pro, Imagen4, etc.)
- Converts each image to smooth animated video
- Synthesizes an ElevenLabs voiceover reading the scene text (this is
  **not** your original voice — see "Audio" below)
- Composites everything together, with captions burned in

### 4. Automatic Download
```
Poll status → Download final video → Ready to upload
```

### 5. Optional: restore original audio
```
AI video + original chapter audio → retimed, remuxed → final.mp4
```
`swap_audio.py` retimes the AI-generated visuals to the real chapter audio's
duration and swaps in the host's actual voice, if you don't want Blotato's
synthesized narration.

## Files Created

### Core Pipeline
- **`ai_scene_generator.py`** - Blotato integration class
  - Scene segmentation + merge-to-20-scenes logic
  - API submission and polling (handles Blotato's real response envelope
    and status values)
  - Video download
  - Loads `BLOTATO_API_KEY` from the skill's `.env` automatically

- **`prepare_scenes.py`** - Step 1: transcript → `scenes.json` (free, no
  network call)
- **`submit_short.py`** - Step 2: `scenes.json` → Blotato job → downloaded
  video (this is what costs credits)
- **`swap_audio.py`** - Optional step 3: restore the original podcast audio

### Documentation
- **`BLOTATO_SETUP.md`** - API key setup, venv setup, and testing
- **`AI_SHORTS_COMPLETE.md`** - This overview

## Quick Start

### 1. Get Blotato API Key
Visit [Blotato Settings → API Keys](https://blotato.com/settings/api-keys)

### 2. Configure

```bash
cd ~/.claude/skills/podcast-video
echo "BLOTATO_API_KEY=your-key-here" >> .env

# one-time: create the venv requests needs (system Python won't allow
# a plain global pip install)
python3 -m venv .venv
.venv/bin/pip install requests
```

### 3. Run (from your podcast assets directory, e.g. `app/assets`)

```bash
# Step 1 — segment (free)
~/.claude/skills/podcast-video/.venv/bin/python3 \
  ~/.claude/skills/podcast-video/shorts/prepare_scenes.py \
  ./shorts/extracted_single/02-how-distillation-works-transcript.json \
  "How Distillation Works" \
  ./shorts/ai_generated/02-how-distillation-works-scenes.json \
  "cinematic technical futuristic"

# --> fill in each scene's "visual_prompt" in the generated scenes.json

# Step 2 — submit (this is what costs Blotato credits)
~/.claude/skills/podcast-video/.venv/bin/python3 \
  ~/.claude/skills/podcast-video/shorts/submit_short.py \
  ./shorts/ai_generated/02-how-distillation-works-scenes.json \
  ./shorts/ai_generated/02-how-distillation-works-AI.mp4

# Step 3 (optional) — restore the real voice
~/.claude/skills/podcast-video/.venv/bin/python3 \
  ~/.claude/skills/podcast-video/shorts/swap_audio.py \
  ./shorts/ai_generated/02-how-distillation-works-AI.mp4 \
  ./shorts/extracted_single/02-how-distillation-works-8-56-to-11-41.m4a \
  ./shorts/ai_generated/02-how-distillation-works-FINAL.mp4
```

### 4. Wait & Download
- **Generation time:** 10-20 minutes (Step 2)
- **Output:** Professional AI-generated vertical video
- **Ready for:** TikTok, Instagram Reels, YouTube Shorts

## Visual Style Examples

### For Technical/AI Content (like "How Distillation Works")
**Style:** `"cinematic technical futuristic"`
- Neural network visualizations
- Data flowing through circuits
- Holographic interfaces
- Sleek tech environments
- Blue/cyan/purple color palette

### For Business/Entrepreneurship
**Style:** `"cinematic modern professional"`
- Office environments
- City skylines
- Professional workspaces
- Graphs and charts
- Clean, corporate aesthetic

### For Creative/Lifestyle
**Style:** `"vibrant colorful dynamic"`
- Bold colors
- Energetic compositions
- People and scenes
- Social media aesthetic
- High contrast

### For Educational/Documentary
**Style:** `"documentary realistic cinematic"`
- Real-world scenes
- Natural environments
- Photographic quality
- Informative visuals
- Neutral tones

## Advanced Customization

### Change AI Image Model
Pass `--model` to `submit_short.py` with one of the values Blotato's API
actually accepts (verified against `GET /v2/videos/templates`):

```
replicate/black-forest-labs/flux-schnell
replicate/black-forest-labs/flux-dev
replicate/black-forest-labs/flux-1.1-pro          # high quality (default)
replicate/black-forest-labs/flux-1.1-pro-ultra
replicate/recraft-ai/recraft-v3                    # realistic imagery
replicate/ideogram-ai/ideogram-v2
replicate/luma/photon
openai/gpt-image-1
fal-ai/nano-banana
fal-ai/nano-banana-2
fal-ai/nano-banana-pro
fal-ai/imagen4/preview/fast                         # Google's model
fal-ai/bytedance/seedream/v4.5/text-to-image
```

Names like `"flux dev"`, `"recraft v3"`, or `"runway gen3"` (marketing
names, not API values) are **rejected** by the API — `submit_short.py`
validates the `--model` flag against the list above before submitting.

### Adjust Scene Duration
Edit the `max_scene_duration` argument passed to
`segment_transcript_into_scenes()` inside `prepare_scenes.py`:

```python
max_scene_duration=8.0   # Slower, more cinematic (default)
max_scene_duration=5.0   # Faster, more energetic
max_scene_duration=10.0  # Very slow, documentary style
```

Note the **20-scene hard cap** still applies regardless of this setting —
longer chapters or shorter `max_scene_duration` values will trigger more
merging.

### Change Aspect Ratio
`submit_short.py --aspect 16:9` (YouTube), `--aspect 1:1` (square),
`--aspect 4:5` (Instagram portrait), or the default `9:16` (vertical).

## Cost Considerations

Blotato pricing varies by plan. For a typical 2-3 minute short:
- Up to 20 AI image generations
- Up to 20 image-to-video animations
- AI voiceover synthesis (if `enableVoiceover` is left on)
- Video compositing and rendering

Check your Blotato plan for current pricing.

## Batch Processing All Chapters

Chapters vary a lot in length — chapter 03 in this repo is ~24 minutes,
which would merge down to 20 scenes of ~70s each under the current
segmentation. That's a different creative problem than a 2-3 minute
chapter, so **don't batch long chapters through this pipeline unchanged**;
either split them into sub-segments first or accept much longer per-scene
visuals.

For chapters in the same ballpark as "How Distillation Works" (2-3 min),
repeat the three-step flow above per chapter:

```bash
cd /path/to/your/podcast/assets

for chapter in 01-intro 02-how-distillation-works; do
  ~/.claude/skills/podcast-video/.venv/bin/python3 \
    ~/.claude/skills/podcast-video/shorts/prepare_scenes.py \
    "./shorts/extracted/${chapter}-transcript.json" \
    "$chapter" \
    "./shorts/ai_generated/${chapter}-scenes.json" \
    "cinematic technical futuristic"
  # fill in visual_prompt fields before continuing to submit_short.py
done
```

**Note:** Even for short chapters, batching all of them will take 1-2 hours
total and consume significant API credits.

## Troubleshooting

### `ModuleNotFoundError: No module named 'requests'`
You're running the system Python, not the skill's venv. Run:
```bash
cd ~/.claude/skills/podcast-video && python3 -m venv .venv && .venv/bin/pip install requests
```
and invoke scripts via `~/.claude/skills/podcast-video/.venv/bin/python3`.

### "BLOTATO_API_KEY not found"
Add your key to `~/.claude/skills/podcast-video/.env` as
`BLOTATO_API_KEY=your-key-here`. It's loaded automatically — no need to
`export` it.

### "Invalid aiImageModel" / "Invalid aspectRatio" etc.
`ai_scene_generator.py` validates these against Blotato's actual enum
values and raises immediately with the allowed list, instead of letting
Blotato reject the request. Use one of the listed values.

### Scenes missing `visual_prompt`
`submit_short.py` refuses to submit until every scene in the `scenes.json`
has a non-empty `visual_prompt`. Fill them in (or have Claude Code do it)
before re-running.

### "Generation failed"
The script now raises as soon as Blotato reports
`creation-from-template-failed`, instead of polling for the full 30-minute
timeout. Check Blotato's status page and your account limits.

### "Timeout"
Increase `timeout` (`submit_short.py --timeout <seconds>`) or check
Blotato's queue status.

### Scenes don't match audio well / big drift after `swap_audio.py`
`swap_audio.py` prints the measured drift between the AI video and the
real audio. If it's more than ~1s, the per-scene pacing has diverged
enough that a simple global retime will look off. In that case, use
Blotato's "Image Slideshow" template instead (stills only, via
`imageUrls`) and composite locally with ffmpeg using the exact transcript
timings — this avoids relying on Blotato's own pacing at all.

### Visual prompts aren't good
Since prompts are now written directly into `scenes.json` (not generated
by an LLM call), just edit the `visual_prompt` field for the scene(s) in
question and re-run `submit_short.py`.

## Integration with Main Podcast Skill

To add this to your main daily workflow:

1. Transcribe full episode → Generate chapters
2. Extract chapter audio segments
3. **NEW:** Generate AI visuals for each chapter
4. Upload to all platforms (horizontal full episode + vertical AI shorts)

This gives you:
- 1 full episode (36 min horizontal with chapters)
- AI-generated shorts (2-3 min vertical, visually stunning) for chapters
  in that length range
- All automated from a single podcast recording

## Next Steps

1. **Set up Blotato API key + venv** (see BLOTATO_SETUP.md)
2. **Test with "How Distillation Works"** chapter
3. **Review the output** and adjust visual style
4. **Batch process** similarly-sized chapters once satisfied
5. **Upload and engage!**

---

**Pro Tip:** The visual prompts live directly in `*_scenes.json` — review
and tweak them per-scene before submitting, rather than editing an LLM
system prompt.
