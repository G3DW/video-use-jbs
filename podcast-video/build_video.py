#!/usr/bin/env python3
"""
Podcast Video Builder - Main Orchestration Script
Automates the complete podcast video production pipeline.
"""

import os
import re
import sys
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

class PodcastVideoBuilder:
    def __init__(self, config_path=None):
        self.script_dir = Path(__file__).parent
        self.config = self.load_config(config_path)
        self.working_dir = Path.cwd()
        self.edit_dir = self.working_dir / "edit"

    def load_config(self, config_path):
        """Load configuration from JSON file"""
        if config_path is None:
            config_path = self.script_dir / "config.json"

        default_config = {
            "video": {
                "trim_end_seconds": 1,
                "waveform_height": 180,
                "waveform_color": "#FFFFFF",
                "waveform_position": 490,
                "resolution": "1280x720",
                "fps": 24,
                "crf": 23,
                "preset": "medium"
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
            },
            "intro": {
                "enabled": True,
                "voice_id": "8579yP6p1e1Pydb8F0dg",
                "model_id": "eleven_v3",
                "gap_seconds": 0.5,
                "loudness_i": "-16",
                "loudness_tp": "-1.5",
                "loudness_lra": "11"
            },
            "outro": {
                "enabled": True,
                "voice_id": "8579yP6p1e1Pydb8F0dg",
                "model_id": "eleven_v3",
                "gap_seconds": 0.5,
                "loudness_i": "-16",
                "loudness_tp": "-1.5",
                "loudness_lra": "11"
            },
            "output": {
                "filename_template": "daily-ai-pulse-{date}-final.mp4"
            }
        }

        if config_path.exists():
            with open(config_path) as f:
                user_config = json.load(f)
                # Merge with defaults
                for key in default_config:
                    if key in user_config:
                        default_config[key].update(user_config[key])

        return default_config

    def find_files(self, audio_path=None, video_path=None):
        """Discover audio and video files in current directory"""
        files = {"audio": None, "video": None, "notes": None}

        if audio_path:
            files["audio"] = Path(audio_path)
        else:
            # Find audio file
            for ext in [".mp3", ".m4a", ".wav"]:
                audio_files = list(self.working_dir.glob(f"*{ext}"))
                if audio_files:
                    files["audio"] = audio_files[0]
                    break

        if video_path:
            files["video"] = Path(video_path)
        else:
            # Find video file (excluding any in edit/ dir)
            video_files = [f for f in self.working_dir.glob("*.mp4")
                          if "edit" not in str(f)]
            if video_files:
                files["video"] = video_files[0]

        # Find notes
        notes_files = list(self.working_dir.glob("*.md"))
        if notes_files:
            files["notes"] = notes_files[0]

        return files

    def setup_directories(self):
        """Create output directory structure"""
        (self.edit_dir / "transcripts").mkdir(parents=True, exist_ok=True)
        (self.edit_dir / "temp").mkdir(exist_ok=True)
        print(f"✓ Created output directories in {self.edit_dir}")

    def transcribe_audio(self, audio_file, skip=False):
        """Transcribe audio using Scribe API"""
        audio_name = audio_file.stem
        cache_file = self.edit_dir / "transcripts" / f"{audio_name}.json"

        if skip and cache_file.exists():
            print(f"✓ Using cached transcript: {cache_file}")
            return cache_file

        if cache_file.exists():
            print(f"  Found existing transcript, using cache")
            return cache_file

        print(f"  Transcribing {audio_file.name}...")

        # Use video-use transcribe helper
        transcribe_script = Path("/Users/joey_makes_stuff/Documents/GitHub/video-use/helpers/transcribe.py")
        venv_python = Path("/Users/joey_makes_stuff/Documents/GitHub/video-use/.venv/bin/python")

        result = subprocess.run(
            [str(venv_python), str(transcribe_script), str(audio_file),
             "--edit-dir", str(self.edit_dir)],
            cwd=str(audio_file.parent),
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"✗ Transcription failed: {result.stderr}")
            return None

        if not cache_file.exists():
            print(f"✗ Transcription reported success but {cache_file} was not created")
            return None

        print(f"✓ Transcribed and cached: {cache_file}")
        return cache_file

    def resolve_intro_audio(self, intro_audio_path=None, intro_text_path=None, no_intro=False):
        """Resolve the intro mp3: explicit flag, generate from text, or auto-discover."""
        if no_intro or not self.config["intro"].get("enabled", True):
            return None

        if intro_audio_path:
            return Path(intro_audio_path)

        temp_dir = self.edit_dir / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        if intro_text_path:
            return self._generate_bookend_from_text(Path(intro_text_path), temp_dir, "intro", self.config["intro"])

        auto_audio = self.working_dir / "intro.mp3"
        if auto_audio.exists():
            print(f"  Found intro audio: {auto_audio.name}")
            return auto_audio

        auto_text = self.working_dir / "intro.txt"
        if auto_text.exists():
            return self._generate_bookend_from_text(auto_text, temp_dir, "intro", self.config["intro"])

        return None

    def resolve_outro_audio(self, outro_audio_path=None, outro_text_path=None, no_outro=False):
        """Resolve the outro mp3: explicit flag, generate from text, or auto-discover.
        Mirrors resolve_intro_audio, but appended to the end of the episode
        instead of prepended — a spoken sign-off / CTA (like, comment,
        subscribe) so the video doesn't just cut off after the last line."""
        if no_outro or not self.config["outro"].get("enabled", True):
            return None

        if outro_audio_path:
            return Path(outro_audio_path)

        temp_dir = self.edit_dir / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        if outro_text_path:
            return self._generate_bookend_from_text(Path(outro_text_path), temp_dir, "outro", self.config["outro"])

        auto_audio = self.working_dir / "outro.mp3"
        if auto_audio.exists():
            print(f"  Found outro audio: {auto_audio.name}")
            return auto_audio

        auto_text = self.working_dir / "outro.txt"
        if auto_text.exists():
            return self._generate_bookend_from_text(auto_text, temp_dir, "outro", self.config["outro"])

        return None

    def _generate_bookend_from_text(self, text_path, temp_dir, label, cfg):
        """Shell out to generate_intro.py to synthesize + master an intro or outro clip.
        generate_intro.py is just text->voice synthesis + mastering, so it's reused
        as-is for outro audio too."""
        output = temp_dir / f"{label}.mp3"

        print(f"  Generating {label} from {text_path.name}...")
        result = subprocess.run(
            [sys.executable, str(self.script_dir / "generate_intro.py"),
             "--text-file", str(text_path),
             "--voice-id", cfg["voice_id"],
             "--model-id", cfg["model_id"],
             "--loudness-i", cfg["loudness_i"],
             "--loudness-tp", cfg["loudness_tp"],
             "--loudness-lra", cfg["loudness_lra"],
             "--output", str(output)],
            capture_output=True, text=True,
        )

        if result.returncode != 0:
            print(f"✗ {label.title()} generation failed: {result.stderr}")
            return None

        print(f"✓ Generated {label}: {output}")
        return output

    def assemble_audio(self, episode_audio, intro_audio=None, outro_audio=None):
        """Concatenate intro? + gap + episode + gap + outro? into one file,
        and persist the intro/content/outro boundaries so downstream steps
        (e.g. the B-roll title-card/caption pass) don't have to re-derive
        them by inspecting the transcript for a gap."""
        if not intro_audio and not outro_audio:
            return episode_audio

        intro_gap = self.config["intro"]["gap_seconds"]
        outro_gap = self.config["outro"]["gap_seconds"]
        combined = self.edit_dir / "temp" / "combined_audio.mp3"

        parts_desc = []
        inputs = []
        concat_inputs = []
        idx = 0

        def add_file(path):
            nonlocal idx
            inputs += ["-i", str(path)]
            concat_inputs.append(f"[{idx}:a]")
            idx += 1

        def add_gap(seconds):
            nonlocal idx
            inputs += ["-f", "lavfi", "-t", str(seconds), "-i", "anullsrc=r=44100:cl=mono"]
            concat_inputs.append(f"[{idx}:a]")
            idx += 1

        if intro_audio:
            add_file(intro_audio)
            add_gap(intro_gap)
            parts_desc.append(f"intro ({intro_audio.name})")
        add_file(episode_audio)
        if outro_audio:
            add_gap(outro_gap)
            add_file(outro_audio)
            parts_desc.append(f"outro ({outro_audio.name})")

        print(f"  Assembling combined audio: {' + '.join(parts_desc)} + episode...")

        filter_complex = "".join(concat_inputs) + f"concat=n={len(concat_inputs)}:v=0:a=1[out]"
        cmd = [
            "ffmpeg", "-y", *inputs,
            "-filter_complex", filter_complex,
            "-map", "[out]", "-c:a", "mp3", "-q:a", "2",
            str(combined),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"✗ Failed to assemble audio: {result.stderr}")
            return None

        # combined_audio.mp3 is rebuilt fresh every run but always has the same
        # name/stem, so any previously cached transcript under that name is now
        # stale (regenerated narration audio has different content/timing).
        stale_cache = self.edit_dir / "transcripts" / f"{combined.stem}.json"
        if stale_cache.exists():
            stale_cache.unlink()
            print(f"  Invalidated stale transcript cache: {stale_cache.name}")

        def duration_of(path):
            probe = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
                capture_output=True, text=True,
            )
            return float(json.loads(probe.stdout)["format"]["duration"])

        meta = {}
        content_start = 0.0
        if intro_audio:
            intro_duration = round(duration_of(intro_audio), 2)
            content_start = round(intro_duration + intro_gap, 2)
            meta["intro_duration"] = intro_duration
            meta["intro_gap_seconds"] = intro_gap
        meta["content_start"] = content_start

        if outro_audio:
            episode_duration = duration_of(episode_audio)
            content_end = round(content_start + episode_duration, 2)
            meta["content_end"] = content_end
            meta["outro_gap_seconds"] = outro_gap
            meta["outro_start"] = round(content_end + outro_gap, 2)

        meta_path = self.edit_dir / "intro_meta.json"
        meta_path.write_text(json.dumps(meta, indent=2))

        print(f"✓ Combined audio: {combined}")
        return combined

    def prepare_video_loop(self, video_file):
        """Trim and create boomerang loop from brand video"""
        trim_seconds = self.config["video"]["trim_end_seconds"]
        temp_dir = self.edit_dir / "temp"

        trimmed = temp_dir / "trimmed.mp4"
        boomerang = temp_dir / "boomerang.mp4"

        print(f"  Preparing brand video loop...")

        # Get duration
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", str(video_file)],
            capture_output=True,
            text=True
        )
        info = json.loads(result.stdout)
        duration = float(info["format"]["duration"])
        trim_duration = duration - trim_seconds

        # Trim
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_file), "-t", str(trim_duration),
             "-c", "copy", str(trimmed)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Create boomerang
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(trimmed),
             "-filter_complex",
             "[0:v]split[fwd][rev];[rev]reverse[reversed];[fwd][reversed]concat=n=2:v=1:a=0,fps=24[out]",
             "-map", "[out]", "-an", "-c:v", "libx264", "-preset", "medium",
             "-crf", "23", str(boomerang)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        print(f"✓ Created boomerang loop: {boomerang}")
        return boomerang

    def resolve_output_filename(self):
        """Resolve the final output filename from the configured template,
        pulling {date} from the working dir name (YYYY-MM-DD-podcast) if present."""
        template = self.config.get("output", {}).get("filename_template", "final.mp4")
        match = re.match(r"(\d{4}-\d{2}-\d{2})-podcast", self.working_dir.name)
        date_str = match.group(1) if match else datetime.now().strftime("%Y-%m-%d")
        return template.format(date=date_str)

    def render_final_video(self, boomerang, audio_file, preview=False):
        """Render final video with waveform overlay"""
        output = self.edit_dir / ("preview.mp4" if preview else self.resolve_output_filename())

        wh = self.config["video"]["waveform_height"]
        wc = self.config["video"]["waveform_color"]
        wp = self.config["video"]["waveform_position"]
        crf = self.config["video"]["crf"]
        preset = self.config["video"]["preset"]

        print(f"  Rendering {'preview' if preview else 'final'} video...")

        filter_complex = (
            f"[1:a]showwaves=s=1024x{wh}:mode=line:rate=24:colors={wc},"
            f"colorchannelmixer=aa=0.9[wave];"
            f"[wave]split[wave1][wave2];"
            f"[wave2]boxblur=2:1[glow];"
            f"[0:v][glow]overlay=(W-w)/2:{wp}[bg];"
            f"[bg][wave1]overlay=(W-w)/2:{wp}:shortest=1[out]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", str(boomerang),
            "-i", str(audio_file),
            "-filter_complex", filter_complex,
            "-map", "[out]", "-map", "1:a",
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-c:a", "aac", "-b:a", "192k",
            str(output)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"✗ Render failed: {result.stderr}")
            return None

        print(f"✓ Rendered: {output}")
        return output

    def generate_transcript_markdown(self, transcript_json, audio_file, output_name=None):
        """Generate readable markdown transcript"""
        if output_name is None:
            output_name = "transcript.md"

        output = self.edit_dir / output_name

        with open(transcript_json) as f:
            data = json.load(f)

        with open(output, 'w') as f:
            f.write(f"# {audio_file.stem.replace('-', ' ').title()}\n\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n")

            # Calculate duration
            if data.get('words'):
                duration_sec = int(data['words'][-1]['end'])
                mins = duration_sec // 60
                secs = duration_sec % 60
                f.write(f"**Duration:** {mins}:{secs:02d}\n\n")

            f.write("---\n\n## Transcript\n\n")
            f.write(data.get('text', ''))

        print(f"✓ Generated transcript: {output}")
        return output

    def generate_chapters(self, transcript_json):
        """Detect topic shifts and generate chapter timestamps"""
        # This uses the same logic from our session
        # Import the chapter detection from our working example

        output = self.edit_dir / "chapters.txt"

        with open(transcript_json) as f:
            data = json.load(f)

        # Use the proven markers from this session
        chapters = self._detect_chapters(data)

        with open(output, 'w') as f:
            for ts_seconds, title in chapters:
                mins = int(ts_seconds // 60)
                secs = int(ts_seconds % 60)
                f.write(f"{mins:02d}:{secs:02d} - {title}\n")

        print(f"✓ Generated chapters: {output}")
        return chapters

    def _detect_chapters(self, transcript_data):
        """Internal chapter detection logic"""
        # Simplified version - in production, this would use semantic analysis
        # For now, return a basic structure
        words = transcript_data.get('words', [])
        if not words:
            return [(0, "Intro")]

        chapters = [(0, "Intro")]

        # Add chapters at ~5-minute intervals for now
        # In production, use the keyword-based detection from our session
        total_duration = words[-1]['end']
        interval = 300  # 5 minutes

        for i in range(1, int(total_duration // interval)):
            target_ts = i * interval
            chapters.append((target_ts, f"Chapter {i+1}"))

        return chapters

    def generate_subtitles(self, transcript_json):
        """Generate SRT subtitle file"""
        output = self.edit_dir / "subtitles.srt"

        with open(transcript_json) as f:
            data = json.load(f)

        words = data.get('words', [])
        subtitles = self._build_subtitle_chunks(words)

        with open(output, 'w', encoding='utf-8') as f:
            for idx, sub in enumerate(subtitles, 1):
                f.write(f"{idx}\n")
                f.write(f"{self._format_srt_time(sub['start'])} --> ")
                f.write(f"{self._format_srt_time(sub['end'])}\n")
                f.write(f"{sub['text']}\n\n")

        print(f"✓ Generated subtitles: {output} ({len(subtitles)} entries)")
        return output

    def _build_subtitle_chunks(self, words):
        """Build subtitle chunks from word-level timestamps"""
        max_words = self.config["subtitles"]["max_words_per_chunk"]
        min_words = self.config["subtitles"]["min_words_for_break"]
        max_chars = self.config["subtitles"]["max_chars_per_line"]

        subtitles = []
        current_chunk = []
        chunk_start = None

        for i, word_obj in enumerate(words):
            word_text = word_obj.get('text', '').strip()
            if not word_text or word_obj.get('type') == 'spacing':
                continue

            if chunk_start is None:
                chunk_start = word_obj['start']

            current_chunk.append(word_text)

            has_punctuation = word_text.rstrip().endswith(('.', '?', '!', ','))
            chunk_length = len(current_chunk)
            is_last_word = (i == len(words) - 1)

            should_break = (
                (has_punctuation and chunk_length >= min_words) or
                chunk_length >= max_words or
                is_last_word
            )

            if should_break and current_chunk:
                chunk_end = word_obj['end']
                chunk_text = ' '.join(current_chunk)

                # Split into lines if needed
                if len(chunk_text) > max_chars:
                    mid = len(chunk_text) // 2
                    split_pos = chunk_text.rfind(' ', mid - 15, mid + 15)
                    if split_pos == -1:
                        split_pos = mid
                    line1 = chunk_text[:split_pos].strip()
                    line2 = chunk_text[split_pos:].strip()
                    formatted_text = f"{line1}\n{line2}"
                else:
                    formatted_text = chunk_text

                subtitles.append({
                    'start': chunk_start,
                    'end': chunk_end,
                    'text': formatted_text
                })

                current_chunk = []
                chunk_start = None

        return subtitles

    def _format_srt_time(self, seconds):
        """Convert seconds to SRT timestamp format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _extract_brief_title(self):
        """Pull the H1 title out of brief.md, if present."""
        brief_path = self.working_dir / "brief.md"
        if not brief_path.exists():
            return None
        for line in brief_path.read_text().splitlines():
            if line.strip().startswith("# "):
                return line.strip()[2:].strip()
        return None

    def _draft_description(self):
        """Draft a YouTube description from brief.md (title + why-now + deep-dive
        summary) plus a standard CTA. Best-effort: brief.md's structure isn't
        rigidly enforced, so this degrades to a placeholder if it can't be parsed."""
        brief_path = self.working_dir / "brief.md"
        if not brief_path.exists():
            return ("(No brief.md found — write a 2-3 sentence summary of the episode here.)\n\n"
                    "---\n\nSubscribe for daily AI news and breakdowns.")

        text = brief_path.read_text()
        lines = text.splitlines()
        title = self._extract_brief_title() or ""

        def section(heading):
            pattern = rf"^##\s*{re.escape(heading)}\s*$"
            capturing = False
            body = []
            for line in lines:
                if re.match(pattern, line.strip(), re.IGNORECASE):
                    capturing = True
                    continue
                if capturing:
                    if line.strip().startswith("## "):
                        break
                    body.append(line)
            return "\n".join(body).strip()

        why_now_match = re.search(r"\*\*Why now:\*\*\s*(.+)", text)
        why_now = why_now_match.group(1).strip() if why_now_match else ""
        deep_dive = section("Deep-dive summary")

        parts = []
        if title:
            parts.append(title)
        if why_now:
            parts.append(why_now)
        if deep_dive:
            parts.append(deep_dive)
        if not parts:
            parts.append("(brief.md found but couldn't be parsed — write a summary here.)")

        parts.append(
            "---\n\n"
            "If this saved you from a bad model bet, like the video and subscribe — "
            "we break down one AI story like this every day.\n\n"
            "Got a model or workflow you want validated? Drop it in the comments."
        )
        return "\n\n".join(parts)

    def generate_upload_info(self, audio_file, chapters, final_video):
        """Generate YouTube upload information document"""
        output = self.edit_dir / "youtube-info.md"

        # Get video info
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", str(final_video)],
            capture_output=True,
            text=True
        )
        info = json.loads(result.stdout)
        duration = float(info["format"]["duration"])
        size_mb = int(info["format"]["size"]) / (1024 * 1024)

        # The chapter detector below is a coarse stub (real topic-shift titles
        # need semantic judgment it doesn't have) — flag it loudly so this
        # never gets uploaded as-is. See podcast-video SKILL.md's mandatory
        # "author real chapters + description" step.
        chapters_are_stub = all(title in ("Intro",) or title.startswith("Chapter ") for _, title in chapters)

        with open(output, 'w') as f:
            f.write(f"# YouTube Upload Information\n\n")
            f.write(f"**Episode:** {audio_file.stem.replace('-', ' ').title()}\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n")
            f.write(f"**Duration:** {int(duration // 60)}:{int(duration % 60):02d}\n")
            f.write(f"**File Size:** {size_mb:.0f} MB\n\n")
            f.write("---\n\n## Description\n\n")
            f.write(self._draft_description())
            f.write("\n\n---\n\n## Chapter Timestamps\n\n")
            if chapters_are_stub:
                f.write("**⚠ AUTO-PLACEHOLDER — replace with real chapters read from transcript.md "
                        "before publishing.**\n\n")
            f.write("```\n")

            for ts, title in chapters:
                if ts == 0:
                    f.write(f"00:00 - {title}\n")
                else:
                    mins = int(ts // 60)
                    secs = int(ts % 60)
                    f.write(f"{mins:02d}:{secs:02d} - {title}\n")

            f.write("```\n\n")
            f.write("## Files\n\n")
            f.write(f"- Video: `{final_video.name}`\n")
            f.write(f"- Subtitles: `subtitles.srt`\n")
            f.write(f"- Transcript: `transcript.md`\n")

        print(f"✓ Generated upload info: {output}")
        if chapters_are_stub:
            print("  ⚠ Chapters are auto-placeholders — author real ones from transcript.md before publishing.")
        return output

    def run(self, audio_path=None, video_path=None, skip_transcribe=False, preview=False,
             intro_audio_path=None, intro_text_path=None, no_intro=False,
             outro_audio_path=None, outro_text_path=None, no_outro=False):
        """Run the complete pipeline"""
        print("\n" + "="*60)
        print("PODCAST VIDEO BUILDER")
        print("="*60 + "\n")

        # 1. Find files
        print("1. Discovering files...")
        files = self.find_files(audio_path, video_path)

        if not files["audio"]:
            print("✗ No audio file found. Place a .mp3 or .m4a in current directory.")
            return False

        if not files["video"]:
            print("✗ No video file found. Place a .mp4 in current directory.")
            return False

        print(f"  Audio: {files['audio'].name}")
        print(f"  Video: {files['video'].name}")
        if files["notes"]:
            print(f"  Notes: {files['notes'].name}")

        # 2. Setup
        print("\n2. Setting up directories...")
        self.setup_directories()

        # 2.5 Intro / outro
        print("\n2.5. Resolving intro/outro...")
        episode_audio = files["audio"]
        intro_audio = self.resolve_intro_audio(intro_audio_path, intro_text_path, no_intro)
        if not intro_audio:
            print("  No intro found, skipping.")
        outro_audio = self.resolve_outro_audio(outro_audio_path, outro_text_path, no_outro)
        if not outro_audio:
            print("  No outro found, skipping.")

        if intro_audio or outro_audio:
            combined = self.assemble_audio(episode_audio, intro_audio, outro_audio)
            if not combined:
                return False
            files["audio"] = combined

        # 3. Transcribe
        print("\n3. Transcribing audio...")
        transcript_json = self.transcribe_audio(files["audio"], skip=skip_transcribe)
        if not transcript_json:
            return False

        # 4. Prepare video
        print("\n4. Preparing brand video...")
        boomerang = self.prepare_video_loop(files["video"])

        # 5. Render
        print("\n5. Rendering final video...")
        final_video = self.render_final_video(boomerang, files["audio"], preview=preview)
        if not final_video:
            return False

        # 6. Generate assets
        print("\n6. Generating YouTube assets...")
        self.generate_transcript_markdown(transcript_json, files["audio"])
        chapters = self.generate_chapters(transcript_json)
        self.generate_subtitles(transcript_json)
        self.generate_upload_info(files["audio"], chapters, final_video)

        print("\n" + "="*60)
        print("✓ COMPLETE! All files ready in ./edit/")
        print("="*60 + "\n")

        return True


def main():
    parser = argparse.ArgumentParser(description="Automated podcast video builder")
    parser.add_argument("--audio", help="Path to audio file")
    parser.add_argument("--video", help="Path to brand video file")
    parser.add_argument("--skip-transcribe", action="store_true",
                       help="Use cached transcript if available")
    parser.add_argument("--preview", action="store_true",
                       help="Render preview (faster, lower quality)")
    parser.add_argument("--config", help="Path to custom config.json")
    parser.add_argument("--intro-audio", help="Path to a pre-generated intro mp3")
    parser.add_argument("--intro-text-file", help="Path to intro script text; will be synthesized via ElevenLabs")
    parser.add_argument("--no-intro", action="store_true", help="Skip the intro step entirely")
    parser.add_argument("--outro-audio", help="Path to a pre-generated outro mp3")
    parser.add_argument("--outro-text-file", help="Path to outro script text; will be synthesized via ElevenLabs")
    parser.add_argument("--no-outro", action="store_true", help="Skip the outro step entirely")

    args = parser.parse_args()

    builder = PodcastVideoBuilder(config_path=args.config)
    success = builder.run(
        audio_path=args.audio,
        video_path=args.video,
        skip_transcribe=args.skip_transcribe,
        preview=args.preview,
        intro_audio_path=args.intro_audio,
        intro_text_path=args.intro_text_file,
        no_intro=args.no_intro,
        outro_audio_path=args.outro_audio,
        outro_text_path=args.outro_text_file,
        no_outro=args.no_outro
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
