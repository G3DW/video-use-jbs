# Blotato AI Short Video Setup

## Get Your API Key

1. Go to [Blotato Settings → API Keys](https://blotato.com/settings/api-keys)
2. Create a new API key
3. Copy the key

## Configure the Key

Add it to your podcast-video skill's `.env` file:

```bash
cd ~/.claude/skills/podcast-video
echo "BLOTATO_API_KEY=your-key-here" >> .env
```

`ai_scene_generator.py` reads this file automatically (via a small built-in
`.env` loader) — you don't need to `export` it or install `python-dotenv`.

## One-time environment setup

The pipeline needs `requests`, which the system Python doesn't have and
(on Homebrew Python 3.14+) refuses to install globally. Use the dedicated
virtualenv instead:

```bash
cd ~/.claude/skills/podcast-video
python3 -m venv .venv
.venv/bin/pip install requests
```

All commands below use `~/.claude/skills/podcast-video/.venv/bin/python3`
rather than the bare `python3` on your PATH.

## Test the Pipeline

The pipeline is two steps, not one. Step 1 segments a chapter transcript
into scenes (no network call, no cost). You (or Claude Code, in-session)
then fill in each scene's `visual_prompt`. Step 2 submits those prompts to
Blotato, which is where cost is incurred.

Once configured, test with the "How Distillation Works" chapter:

```bash
cd /path/to/your/podcast/assets   # e.g. app/assets in this repo

# Step 1: segment the transcript into scenes.json (free, instant)
~/.claude/skills/podcast-video/.venv/bin/python3 \
  ~/.claude/skills/podcast-video/shorts/prepare_scenes.py \
  ./shorts/extracted_single/02-how-distillation-works-transcript.json \
  "How Distillation Works" \
  ./shorts/ai_generated/02-how-distillation-works-scenes.json \
  "cinematic technical futuristic"

# --> now open the scenes.json and fill in every "visual_prompt" field

# Step 2: submit to Blotato, poll, and download (this is what costs credits)
~/.claude/skills/podcast-video/.venv/bin/python3 \
  ~/.claude/skills/podcast-video/shorts/submit_short.py \
  ./shorts/ai_generated/02-how-distillation-works-scenes.json \
  ./shorts/ai_generated/02-how-distillation-works-AI.mp4
```

This will:
- Segment the 2:45 chapter into up to 20 scenes (5-13s each; scenes are
  merged, never dropped, if segmentation initially produces more than 20 —
  Blotato's hard cap)
- Submit your visual prompts to Blotato for AI image generation + animation
- Poll until the job is `done` (or raise immediately on
  `creation-from-template-failed`, rather than waiting out the full timeout)
- Download the final rendered video

**Estimated time:** 10-20 minutes for generation
**Cost:** Varies by plan, check Blotato pricing for AI image + video generation

### Important: the voiceover is not your audio

Blotato's "AI Video with AI Voice" template always narrates with a
synthesized ElevenLabs voice (default "Brian, American, deep") — it cannot
use the original podcast audio. If you want the real voice in the final
short, run one more step after `submit_short.py`:

```bash
~/.claude/skills/podcast-video/.venv/bin/python3 \
  ~/.claude/skills/podcast-video/shorts/swap_audio.py \
  ./shorts/ai_generated/02-how-distillation-works-AI.mp4 \
  ./shorts/extracted_single/02-how-distillation-works-8-56-to-11-41.m4a \
  ./shorts/ai_generated/02-how-distillation-works-FINAL.mp4
```

This retimes the AI-generated visuals to the real audio's duration and
mutes the ElevenLabs voice. It prints the measured drift between the two;
if drift exceeds ~1s the visuals may noticeably desync from the narration
(see AI_SHORTS_COMPLETE.md for the fallback approach in that case).

## Visual Style Options

Try different aesthetics:
- `"cinematic technical"` - Sleek tech visuals, neural networks, data flows
- `"futuristic sci-fi"` - Holograms, neon, digital environments
- `"abstract minimalist"` - Clean shapes, geometric, modern
- `"documentary realistic"` - Real-world scenes, photographic
- `"vibrant colorful"` - Bold colors, energetic, social media style

## Customization

`submit_short.py` flags:
- `--model` - AI image model. Must be one of the values Blotato actually
  accepts (see `VALID_AI_IMAGE_MODELS` in `ai_scene_generator.py`), e.g.
  `replicate/black-forest-labs/flux-1.1-pro`, `replicate/black-forest-labs/flux-dev`,
  `replicate/recraft-ai/recraft-v3`, `fal-ai/imagen4/preview/fast`.
  (Model names like `"flux dev"` or `"runway gen3"` are **not** valid API
  values — those are just marketing names.)
- `--aspect` - `"16:9"`, `"1:1"`, `"4:5"`, or `"9:16"` (default)
- `--no-animate` - skip image-to-video animation, use static images
- `--voice` - which ElevenLabs voice to use if you keep the AI voiceover
- `--no-voiceover` - disable Blotato's voiceover entirely (captions still
  burn in from the `script` text either way)

`prepare_scenes.py`: edit `max_scene_duration` in
`ai_scene_generator.py`'s `segment_transcript_into_scenes` call — shorter
(5s) for faster pace, longer (10s) for cinematic.
