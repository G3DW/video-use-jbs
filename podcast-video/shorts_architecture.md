# Short-Form Content Generator - Architecture

## Goal
Generate 7 vertical short-form videos (1080×1920) from podcast chapters, each with:
- Custom intro card (2-3s)
- Animated word-by-word captions
- Chapter-specific visual theme
- Progress indicator
- Outro card with CTA (2-3s)

## Input
- Chapter timestamps from main video
- Full transcript with word-level timing
- Audio file
- Brand assets

## Output (per chapter)
```
shorts/
├── chapter-1-intro.mp4              (0:00-8:56)
├── chapter-2-distillation.mp4       (8:56-11:41)
├── chapter-3-pricing-war.mp4        (11:41-16:40)
├── chapter-4-micro-distillation.mp4 (16:40-21:56)
├── chapter-5-operator-framework.mp4 (21:56-29:02)
├── chapter-6-portability.mp4        (29:02-33:03)
└── chapter-7-recap.mp4              (33:03-36:29)
```

## Visual Components

### 1. Intro Card (2-3 seconds)
```
┌─────────────────┐
│                 │
│   [Brand Logo]  │
│                 │
│  Chapter Title  │
│   "How It      │
│   Works"       │
│                 │
│  [Visual Icon] │
│                 │
└─────────────────┘
```

### 2. Main Content Layer
```
┌─────────────────┐
│   [Progress]    │  <- Thin bar at top
│                 │
│                 │
│  [Background]   │  <- Cropped/repositioned for 9:16
│  with slight    │
│  blur overlay   │
│                 │
│  ┌──────────┐   │
│  │Animated  │   │  <- Word-by-word captions
│  │Caption   │   │     2-3 lines, centered
│  │Here      │   │
│  └──────────┘   │
│                 │
│  [Waveform]     │  <- Subtle, centered
│                 │
│  Chapter 2/7    │  <- Small indicator
└─────────────────┘
```

### 3. Outro Card (2-3 seconds)
```
┌─────────────────┐
│                 │
│  "Full Episode" │
│     Available   │
│                 │
│   [QR Code or  │
│    Link Text]   │
│                 │
│  @YourHandle    │
│                 │
└─────────────────┘
```

## Animation Styles

### Caption Animation Options
1. **Pop-In** (MrBeast style)
   - Word appears with scale spring (0.8 → 1.0)
   - Yellow highlight background
   - Bold sans-serif font

2. **Highlight Wave** (Alex Hormozi style)
   - All words visible, gray
   - Current word: white + yellow background
   - Wave effect across sentence

3. **Typewriter** (Clean professional)
   - Words appear left-to-right
   - Minimal animation
   - White text with subtle shadow

**We'll use:** Hybrid - Pop-in with highlight for current word

### Timing
- Each word visible for its duration + 100ms
- Next word appears 50ms before current finishes (overlap)
- Max 3 lines on screen at once
- Previous words fade to 60% opacity

## Technical Stack

### Rendering Approach
Use **HyperFrames** for caption animations (HTML/CSS/GSAP):
- Word-level timing precision
- Professional animation easing
- Fast iteration on styles
- Deterministic frame capture

### Workflow
```
1. Extract chapter audio segment
2. Get word timestamps for that segment
3. Generate intro card (PIL or HyperFrames)
4. Generate outro card (PIL or HyperFrames)
5. Render main content:
   - Background: FFmpeg crop/scale to 1080×1920
   - Captions: HyperFrames HTML → video
   - Waveform: FFmpeg overlay
6. Concat: intro + main + outro
```

## Chapter Themes

Each chapter gets visual identity:

| Chapter | Theme Color | Icon/Visual | Vibe |
|---------|-------------|-------------|------|
| Intro | Blue (#0080FF) | Lightbulb | Curiosity |
| How It Works | Purple (#8B5CF6) | Gears | Technical |
| Pricing War | Red (#EF4444) | Chart Down | Urgency |
| Micro-Distillation | Green (#10B981) | Puzzle | Solution |
| Operator Framework | Orange (#F97316) | Dashboard | Strategy |
| Portability | Cyan (#06B6D4) | Arrows | Future |
| Recap | Yellow (#FBBF24) | Checkmark | Summary |

## Configuration Schema

```json
{
  "shorts": {
    "format": {
      "width": 1080,
      "height": 1920,
      "fps": 30
    },
    "intro": {
      "duration": 2.5,
      "show_chapter_number": true,
      "animation": "fade-in"
    },
    "captions": {
      "style": "pop-in-highlight",
      "font": "Montserrat",
      "font_size": 72,
      "max_lines": 3,
      "background_color": "#FFEB3B",
      "text_color": "#000000",
      "shadow": true
    },
    "outro": {
      "duration": 3,
      "show_qr": false,
      "cta_text": "Full Episode Available",
      "handle": "@YourPodcast"
    },
    "progress_bar": {
      "enabled": true,
      "height": 4,
      "color": "#FFFFFF",
      "position": "top"
    }
  }
}
```

## File Structure

```
~/.claude/skills/podcast-video/
├── shorts/
│   ├── render_shorts.py          # Main orchestrator
│   ├── extract_chapters.py       # Audio/transcript segmentation
│   ├── create_cards.py           # Intro/outro card generator
│   ├── safe_zones.json           # Canonical cross-platform (TikTok ∩ Reels/FB) safe-zone margins
│   ├── hyperframes_overlays/     # HyperFrames overlay templates, safe-zone-aware
│   │   ├── safe-zone.css         # --safe-* custom props + .safe-zone class, filled from safe_zones.json
│   │   ├── captions.html         # word-by-word captions, pinned to safe-zone bottom edge
│   │   ├── lower-third.html      # title/subtitle bar
│   │   └── chapter-badge.html    # "Chapter N/Total" indicator
│   ├── themes.json               # Chapter visual themes
│   └── config.json               # Shorts config
```

## Integration Point

Extend main skill with `--shorts` flag:

```bash
~/.claude/skills/podcast-video/build_video.py --shorts
```

Or standalone:

```bash
~/.claude/skills/podcast-video/shorts/render_shorts.py
```

## Output Naming

```
shorts/
├── 01-intro-0-00-to-8-56.mp4
├── 02-how-distillation-works-8-56-to-11-41.mp4
├── 03-pricing-war-11-41-to-16-40.mp4
├── 04-micro-distillation-16-40-to-21-56.mp4
├── 05-operator-framework-21-56-to-29-02.mp4
├── 06-portability-29-02-to-33-03.mp4
└── 07-recap-33-03-to-36-29.mp4
```

## Quality Targets

- **Resolution:** 1080×1920 (9:16)
- **Frame rate:** 30fps (smooth captions)
- **Bitrate:** ~2500 kbps (high quality for social)
- **Audio:** AAC 192 kbps, 44.1kHz
- **Caption readability:** Minimum 2s per caption chunk
- **File size:** ~10-20 MB per minute

## Testing Strategy

1. Build intro card generator first (static, fast)
2. Build caption renderer with HyperFrames
3. Test on Chapter 2 (How Distillation Works - 2:45 duration)
4. Iterate on animation timing
5. Add outro card
6. Add progress bar
7. Apply themes to all chapters
8. Batch render all 7

---

**Next:** Implement each component
