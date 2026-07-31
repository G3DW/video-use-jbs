# Podcast Video Production Skill

Fully automated daily podcast video builder for YouTube.

## Quick Start

```bash
cd your-podcast-episode-folder/
# Place your files:
# - episode.mp3 (your audio)
# - brand-loop.mp4 (your logo/brand video)

# Run the skill
~/.claude/skills/podcast-video/build_video.py

# Or use Claude Code
/podcast-video
```

## What You Get

In `./edit/`:
- ✅ `final.mp4` - Upload-ready video with waveform
- ✅ `subtitles.srt` - Word-synced YouTube subtitles
- ✅ `transcript.md` - Full episode transcript
- ✅ `youtube-info.md` - Chapters + description template

## Installation

The skill is already installed at `~/.claude/skills/podcast-video/`

### Requirements

1. **FFmpeg** - Video processing
   ```bash
   brew install ffmpeg
   ```

2. **Python 3.8+** - Already have it

3. **ElevenLabs API Key** - For transcription
   - Get one at https://elevenlabs.io
   - Set in environment: `export ELEVENLABS_API_KEY=your_key`
   - Or add to `~/.claude/skills/podcast-video/.env`:
     ```
     ELEVENLABS_API_KEY=your_key_here
     ```

4. **video-use repo** - Already cloned and configured

## Usage Modes

### Basic (Auto-detect files)
```bash
cd podcast-folder/
~/.claude/skills/podcast-video/build_video.py
```

### Specify files
```bash
~/.claude/skills/podcast-video/build_video.py \
  --audio episode-042.mp3 \
  --video my-brand.mp4
```

### Preview mode (fast)
```bash
~/.claude/skills/podcast-video/build_video.py --preview
```

### Use cached transcript
```bash
~/.claude/skills/podcast-video/build_video.py --skip-transcribe
```

## Configuration

Edit `~/.claude/skills/podcast-video/config.json`:

```json
{
  "video": {
    "waveform_height": 180,        // Pixel height
    "waveform_color": "#FFFFFF",   // Hex color
    "waveform_position": 490,      // Y position from top
    "crf": 23                      // Quality (18=best, 28=smaller)
  },
  "chapters": {
    "min_chapters": 3,
    "max_chapters": 7
  }
}
```

## Brand Video Guidelines

Your brand loop should:
- ✅ Be 5-10 seconds long
- ✅ Have no black frames at end
- ✅ Look good when reversed (boomerang effect)
- ✅ Be 1280×720 or higher resolution

## Output Specifications

**Video:**
- Resolution: 1280×720 (720p)
- Frame rate: 24 fps
- Codec: H.264
- Quality: CRF 23 (high quality, ~1300 kbps)

**Audio:**
- Codec: AAC-LC
- Bitrate: 192 kbps
- Sample rate: 44.1 kHz stereo

**Subtitles:**
- Format: SRT (SubRip)
- Timing: Word-level accuracy
- Style: Max 2 lines, 42 chars/line

## Workflow Details

1. **Discovery** - Finds audio + video in current directory
2. **Transcription** - Sends to Scribe API (cached locally)
3. **Video Prep** - Trims black frames, creates boomerang
4. **Render** - Composites background + waveform + audio
5. **Analysis** - Detects topic shifts for chapters
6. **Subtitles** - Generates word-synced SRT
7. **Packaging** - Assembles upload info

**Typical runtime:** 5-8 minutes for 30-minute episode

## Troubleshooting

### "No audio file found"
Place a `.mp3` or `.m4a` in the current directory.

### "No video file found"
Place a `.mp4` brand loop in the current directory.

### "Transcription failed"
- Check `ELEVENLABS_API_KEY` is set
- Verify API quota at elevenlabs.io
- Check internet connection

### Waveform too dim
Edit `config.json`:
```json
"waveform_color": "#00D9FF"  // Use brighter color
```

### Video/audio out of sync
This shouldn't happen with word-level timestamps. If it does:
1. Re-run with `--skip-transcribe` to use fresh cache
2. Check audio file isn't corrupted
3. Report as bug

## Advanced Features

### Custom Chapter Detection

Edit `~/.claude/skills/podcast-video/detect_chapters.py` to customize topic markers:

```python
ai_markers = [
    (["your", "keyword", "phrase"], "Chapter Title"),
    (["another", "topic", "shift"], "Another Chapter"),
]
```

### Multiple Waveform Styles

Create presets in `config.json`:
```json
{
  "presets": {
    "tech": {
      "waveform_color": "#00D9FF",
      "waveform_height": 180
    },
    "minimal": {
      "waveform_color": "#FFFFFF",
      "waveform_height": 120
    }
  }
}
```

### Batch Processing

```bash
for dir in 2026-07-*/; do
  cd "$dir"
  ~/.claude/skills/podcast-video/build_video.py
  cd ..
done
```

## File Structure

```
~/.claude/skills/podcast-video/
├── SKILL.md              # Skill metadata
├── README.md             # This file
├── config.json           # Configuration
├── build_video.py        # Main script
├── detect_chapters.py    # Chapter detection
└── .env                  # API keys (create this)
```

## Performance Tips

1. **Use preview mode** during testing (`--preview`)
2. **Cache transcripts** with `--skip-transcribe`
3. **Lower CRF** for smaller files (25-28)
4. **Faster preset** in config: `"preset": "fast"`

## Integration with Claude Code

When you invoke `/podcast-video` in Claude Code, it:
1. Confirms the current directory
2. Lists discovered files
3. Asks for episode title
4. Runs the pipeline
5. Reports completion with file locations

## Future Enhancements

Planned features:
- [ ] Auto-upload to YouTube
- [ ] Chapter thumbnails
- [ ] Speaker diarization overlays
- [ ] Multi-language subtitles
- [ ] Intro/outro injection
- [ ] Social media clip extraction

## Support

Issues? Create an issue or contact the maintainer.

## Credits

Built on the `video-use` framework.
- ElevenLabs Scribe API for transcription
- FFmpeg for video processing

---

**Version:** 1.0.0
**Author:** Generated from successful podcast production session
**Last Updated:** 2026-07-24
