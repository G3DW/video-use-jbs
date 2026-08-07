# Building Short-Form Content - Complete Guide

## Overview

This system automatically generates 7 vertical short-form videos (9:16) from your podcast chapters, each with:
- ✅ Animated intro card (2.5s) with chapter theme
- ✅ Word-by-word animated captions synced to audio
- ✅ Vertical waveform visualization
- ✅ Outro card with CTA (3s)
- ✅ Chapter-specific color theming

## Quick Start

### From existing podcast video:

```bash
cd your-podcast-folder/

# 1. Build main video first (if not already done)
~/.claude/skills/podcast-video/build_video.py

# 2. Generate short-form clips
python3 ~/.claude/skills/podcast-video/shorts/build_all_shorts.py \
  edit/transcripts/your-episode.json \
  edit/youtube-info.md \
  your-episode.mp3
```

This will create `./shorts/final/` with 7 videos ready to upload.

## Step-by-Step Workflow

### Step 1: Extract Chapters

```bash
python3 ~/.claude/skills/podcast-video/shorts/extract_chapters.py \
  your-audio.mp3 \
  edit/transcripts/your-audio.json \
  chapters.json \
  ./shorts/extracted
```

**chapters.json format:**
```json
[
  [0, "Intro"],
  [536, "How Distillation Works"],
  [701, "The Pricing War"],
  ...
]
```

**Output:**
```
shorts/extracted/
├── 01-intro-0-00-to-8-56.m4a
├── 01-intro-transcript.json
├── 02-how-distillation-works-8-56-to-11-41.m4a
├── 02-how-distillation-works-transcript.json
...
└── chapters_index.json
```

### Step 2: Render Short-Form Videos

```bash
python3 ~/.claude/skills/podcast-video/shorts/render_shorts.py \
  shorts/extracted/chapters_index.json \
  shorts/final
```

**Output:**
```
shorts/final/
├── 01-intro-0-00-to-8-56.mp4           (8:56 + 5.5s cards = 9:01)
├── 02-how-distillation-works-...mp4    (2:45 + 5.5s cards = 2:50)
├── 03-pricing-war-...mp4
├── 04-micro-distillation-...mp4
├── 05-operator-framework-...mp4
├── 06-portability-...mp4
└── 07-recap-...mp4
```

## What Gets Created (Per Chapter)

```
Timeline:
[Intro Card 2.5s] → [Animated Captions + Audio] → [Outro Card 3s]

Visual Layers:
1. Black background (1080×1920)
2. Vertical waveform (centered, subtle)
3. Animated captions (word-by-word pop-in)
4. Progress bar (optional, top)
```

## Customization

### Edit Configuration

`~/.claude/skills/podcast-video/shorts/config.json`:

```json
{
  "format": {
    "width": 1080,
    "height": 1920,
    "fps": 30
  },
  "intro": {
    "duration": 2.5,
    "show_chapter_number": true
  },
  "captions": {
    "font_size": 72,
    "background_color": "#FFEB3B",
    "text_color": "#FFFFFF"
  },
  "outro": {
    "duration": 3.0,
    "cta_text": "Full Episode Available",
    "handle": "@dailyaipulse"
  },
  "brand": {
    "name": "Daily AI Pulse"
  }
}
```

### Chapter Themes

Edit `shorts/create_cards.py` to customize chapter colors and icons:

```python
THEMES = {
    "Your Chapter Title": {"color": "#FF5A00", "icon": "🔥"},
    ...
}
```

### Caption Styles

Edit `shorts/hyperframes_overlays/captions.html` for different animation styles:
- Change font family
- Adjust animation timing
- Modify highlight colors
- Add effects

Caption text is pinned to the bottom edge of the cross-platform safe
zone (`shorts/safe_zones.json`), not centered, so it clears both
TikTok's and Instagram/Facebook Reels' UI chrome after repost. Don't
move the caption container out of `.safe-zone` without checking the
margins in `safe_zones.json` first — see `hyperframes_overlays/safe-zone.css`.

## Requirements

### Software
- **FFmpeg** - video processing
- **Python 3.8+** - with PIL (Pillow)
- **Node.js** - for HyperFrames (caption animations)

### Install Dependencies

```bash
# Python
pip install Pillow

# HyperFrames (auto-installed via npx on first use)
# Or install globally:
npm install -g hyperframes
```

## Testing Individual Components

### Test Card Generation

```bash
python3 ~/.claude/skills/podcast-video/shorts/create_cards.py
```

Outputs test cards to `./shorts/cards_test/`

### Test Chapter Extraction

```bash
# Extract just one chapter
python3 ~/.claude/skills/podcast-video/shorts/extract_chapters.py \
  audio.mp3 transcript.json \
  '[["536", "Test Chapter"]]' \
  ./shorts/test
```

## Output Specifications

**Video Format:**
- Resolution: 1080×1920 (9:16 portrait)
- Frame rate: 30 fps
- Codec: H.264
- Quality: CRF 23
- Bitrate: ~2000-2500 kbps

**Audio:**
- Codec: AAC-LC
- Bitrate: 192 kbps
- Sample rate: 44.1 kHz

**File Sizes (approximate):**
- 1 minute: ~15-20 MB
- 3 minutes: ~45-60 MB
- 5 minutes: ~75-100 MB

## Platform Upload Recommendations

### Instagram Reels
- Max length: 90 seconds
- Use chapters 2-7 (skip intro if too long)
- Add platform-specific hashtags in caption

### TikTok
- Max length: 10 minutes
- All chapters work
- Add text overlay with chapter number

### YouTube Shorts
- Max length: 60 seconds
- Best: chapters 2-5 (focused topics)
- Link to full episode in description

### Facebook/LinkedIn
- Max length: varies
- All chapters work
- Add context in post text

## Batch Processing

Process all chapters at once:

```bash
#!/bin/bash
# build_all_shorts.sh

AUDIO=$1
TRANSCRIPT=$2
CHAPTERS=$3

# Extract
python3 ~/.claude/skills/podcast-video/shorts/extract_chapters.py \
  "$AUDIO" "$TRANSCRIPT" "$CHAPTERS" ./shorts/extracted

# Render
python3 ~/.claude/skills/podcast-video/shorts/render_shorts.py \
  ./shorts/extracted/chapters_index.json \
  ./shorts/final

echo "✓ All shorts ready in ./shorts/final/"
```

## Troubleshooting

### "HyperFrames render failed"
- **Fallback:** System creates transparent placeholder
- **Fix:** Install HyperFrames: `npm install -g hyperframes`
- **Or:** Use static captions (edit render_shorts.py)

### "ModuleNotFoundError: PIL"
```bash
pip install Pillow
```

### Cards look wrong
- Check font paths in `create_cards.py`
- System fonts may vary - update font paths for your OS

### Captions out of sync
- Verify transcript has correct word-level timestamps
- Check `extract_chapters.py` time offset calculation

### Video quality too low
- Increase bitrate in render_shorts.py
- Lower CRF value (18 = higher quality)

## Performance

**Per chapter render time:**
- Intro/outro cards: ~5 seconds
- Caption animation: ~10-30 seconds (HyperFrames)
- Background + waveform: ~10-20 seconds
- Compositing: ~5-10 seconds
- **Total:** ~30-60 seconds per minute of content

**Full 7-chapter batch:**
- Total render time: ~10-15 minutes
- Parallel rendering: ~5-8 minutes (if implemented)

## Advanced Features

### Add Progress Bar

Edit `render_shorts.py` to overlay progress bar:

```python
# In compositing step
"-vf", "drawbox=x=0:y=0:w=iw*{progress}:h=4:color=white@0.8"
```

### Custom Animations

Replace HyperFrames with:
- **Remotion** - React-based animations
- **Manim** - Mathematical animations
- **After Effects** - via scripting

### Speaker Diarization

Add speaker labels to captions:
- Use transcript `speaker_id` field
- Color-code different speakers
- Add speaker name overlays

---

## Example: Today's Episode

From our session, this would create:

1. **Intro** (8:56) → 9:01 with cards
2. **How Distillation Works** (2:45) → 2:50
3. **The Pricing War** (4:59) → 5:04
4. **Micro-Distillation** (5:16) → 5:21
5. **Operator Framework** (7:06) → 7:11
6. **Portability** (4:01) → 4:06
7. **Recap** (3:26) → 3:31

**Total:** 7 videos ready for Instagram Reels, TikTok, YouTube Shorts

---

**Ready to create shorts?** Run the extraction and render pipeline!
