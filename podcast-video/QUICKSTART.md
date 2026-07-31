# Quick Start Guide - Podcast Video Skill

## First Time Setup (2 minutes)

### 1. Set your ElevenLabs API key

Create `.env` file:
```bash
echo "ELEVENLABS_API_KEY=your_key_here" > ~/.claude/skills/podcast-video/.env
```

Or add to your shell profile:
```bash
export ELEVENLABS_API_KEY=your_key_here
```

### 2. Verify dependencies

```bash
# Check FFmpeg
ffmpeg -version

# If missing:
brew install ffmpeg
```

That's it! You're ready to go.

---

## Daily Workflow

### Step 1: Organize your files

```bash
cd ~/podcasts/daily-pulse/2026-07-24/

# You should have:
# - your-episode.mp3 (or .m4a)
# - your-brand-loop.mp4
```

### Step 2: Run the skill

**Option A - From command line:**
```bash
~/.claude/skills/podcast-video/build_video.py
```

**Option B - In Claude Code:**
```
/podcast-video
```

### Step 3: Wait 5-8 minutes

The skill will:
- ✓ Transcribe your audio (cached for re-runs)
- ✓ Create boomerang background loop
- ✓ Render video with waveform
- ✓ Detect chapter timestamps
- ✓ Generate word-synced subtitles
- ✓ Package upload info

### Step 4: Upload to YouTube

All files are in `./edit/`:

1. **Upload `final.mp4`** to YouTube
2. **Add chapters** from `youtube-info.md` to description
3. **Upload `subtitles.srt`** in YouTube Studio → Subtitles
4. **Copy description template** from `youtube-info.md`

Done! 🎉

---

## Example Session

```bash
$ cd ~/podcasts/daily-pulse/2026-07-24/

$ ls
niche-pulse-ai-distillation-2026-07-24.mp3
jbs-loop-video-hd.mp4

$ ~/.claude/skills/podcast-video/build_video.py

============================================================
PODCAST VIDEO BUILDER
============================================================

1. Discovering files...
  Audio: niche-pulse-ai-distillation-2026-07-24.mp3
  Video: jbs-loop-video-hd.mp4

2. Setting up directories...
✓ Created output directories in ./edit

3. Transcribing audio...
  Transcribing niche-pulse-ai-distillation-2026-07-24.mp3...
✓ Transcribed and cached: ./edit/transcripts/...json

4. Preparing brand video...
  Preparing brand video loop...
✓ Created boomerang loop: ./edit/temp/boomerang.mp4

5. Rendering final video...
  Rendering final video...
✓ Rendered: ./edit/final.mp4

6. Generating YouTube assets...
✓ Generated transcript: ./edit/transcript.md
✓ Generated chapters: ./edit/chapters.txt
✓ Generated subtitles: ./edit/subtitles.srt (678 entries)
✓ Generated upload info: ./edit/youtube-info.md

============================================================
✓ COMPLETE! All files ready in ./edit/
============================================================

$ ls edit/
final.mp4  subtitles.srt  transcript.md  youtube-info.md
```

---

## Tips for Speed

### Use preview mode while testing
```bash
~/.claude/skills/podcast-video/build_video.py --preview
```
Renders at 720p with faster encoding. Good for checking composition.

### Skip re-transcribing
```bash
~/.claude/skills/podcast-video/build_video.py --skip-transcribe
```
Uses cached transcript if audio hasn't changed.

### Combine flags
```bash
~/.claude/skills/podcast-video/build_video.py --preview --skip-transcribe
```
Fast iteration during editing.

---

## Customization

### Change waveform color

Edit `~/.claude/skills/podcast-video/config.json`:
```json
{
  "video": {
    "waveform_color": "#00D9FF"  // Cyan
  }
}
```

Common colors:
- `#FFFFFF` - White (default)
- `#00D9FF` - Bright cyan
- `#FF5A00` - Orange
- `#00FF00` - Green

### Adjust waveform size

```json
{
  "video": {
    "waveform_height": 220,     // Taller
    "waveform_position": 470    // Higher on screen
  }
}
```

### Change video quality

```json
{
  "video": {
    "crf": 20  // Higher quality, larger file (18-28 range)
  }
}
```

---

## Troubleshooting

### Error: "No audio file found"
**Solution:** Place a `.mp3` or `.m4a` file in current directory

### Error: "No video file found"
**Solution:** Place a `.mp4` brand loop in current directory

### Error: "Transcription failed"
**Solution:** Check your ElevenLabs API key:
```bash
cat ~/.claude/skills/podcast-video/.env
# Should show: ELEVENLABS_API_KEY=sk_...
```

### Waveform is too dim
**Solution:** Use a brighter color in `config.json`:
```json
"waveform_color": "#00FFFF"
```

### Video looks choppy
**Solution:** Check your brand video has no black frames:
```bash
ffprobe -v error -show_frames jbs-loop-video-hd.mp4 | grep pict_type
```

### Chapters aren't accurate
**Solution:** Chapters are auto-detected. You can manually edit them in `edit/youtube-info.md` before uploading.

---

## Next Steps

Once you're comfortable with the basic workflow:

1. **Create presets** for different show types
2. **Batch process** multiple episodes
3. **Customize chapter detection** for your content
4. **Set up keyboard shortcuts** for the build command

---

Need help? Check `README.md` for full documentation or report issues.
