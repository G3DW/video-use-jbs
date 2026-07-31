#!/usr/bin/env python3
"""
Short-Form Video Renderer - Main orchestrator for creating vertical clips
"""

import json
import subprocess
import sys
from pathlib import Path
import shutil

# Import our modules
import create_cards
import extract_chapters


class ShortsRenderer:
    def __init__(self, config_path=None):
        self.script_dir = Path(__file__).parent
        self.config = self.load_config(config_path)

    def load_config(self, config_path):
        """Load shorts configuration"""
        default_config = {
            "format": {
                "width": 1080,
                "height": 1920,
                "fps": 30
            },
            "intro": {
                "duration": 2.5,
                "show_chapter_number": True
            },
            "captions": {
                "style": "pop-in-highlight",
                "font_size": 72,
                "max_lines": 3,
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

        if config_path and Path(config_path).exists():
            with open(config_path) as f:
                user_config = json.load(f)
                # Merge
                for key in user_config:
                    if key in default_config and isinstance(default_config[key], dict):
                        default_config[key].update(user_config[key])
                    else:
                        default_config[key] = user_config[key]

        return default_config

    def render_caption_video(self, transcript_file, output_path, duration):
        """
        Render animated captions using HyperFrames

        Args:
            transcript_file: JSON with word-level timing
            output_path: Where to save caption video
            duration: Total duration in seconds
        """
        with open(transcript_file) as f:
            data = json.load(f)

        words = data.get('words', [])

        # Filter out spacing
        text_words = [w for w in words if w.get('type') != 'spacing']

        # Prepare word data for JavaScript
        word_data = []
        for word in text_words:
            word_data.append({
                "text": word.get('text', '').strip(),
                "start": word.get('start', 0),
                "end": word.get('end', 0)
            })

        # Load HTML template
        template_path = self.script_dir / "captions_hyperframes" / "template.html"
        with open(template_path) as f:
            html_content = f.read()

        # Inject word data
        html_content = html_content.replace(
            "{{WORDS_DATA}}",
            json.dumps(word_data)
        )
        html_content = html_content.replace(
            "{{DURATION}}",
            str(duration)
        )

        # Write customized HTML
        temp_html = self.script_dir / "captions_hyperframes" / "temp_render.html"
        with open(temp_html, 'w') as f:
            f.write(html_content)

        # Render with HyperFrames
        print("    Rendering captions with HyperFrames...")

        fps = self.config["format"]["fps"]
        width = self.config["format"]["width"]
        height = self.config["format"]["height"]

        # Use npx to run HyperFrames (or direct command if installed)
        cmd = [
            "npx", "--yes", "hyperframes", "render",
            str(self.script_dir / "captions_hyperframes"),
            "-o", str(output_path),
            "--fps", str(fps),
            "--width", str(width),
            "--height", str(height),
            "--duration", str(duration),
            "--format", "mp4"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"    ✗ HyperFrames render failed: {result.stderr}")
            # Fallback: create transparent video with ffmpeg
            return self.create_transparent_placeholder(output_path, duration)

        print(f"    ✓ Captions rendered: {output_path}")
        return output_path

    def create_transparent_placeholder(self, output_path, duration):
        """Create transparent video as fallback"""
        width = self.config["format"]["width"]
        height = self.config["format"]["height"]
        fps = self.config["format"]["fps"]

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i",
            f"color=c=black@0.0:s={width}x{height}:d={duration}:r={fps}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(output_path)
        ]

        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_path

    def render_chapter_short(self, chapter_info, chapters_dir, output_path):
        """
        Render complete short-form video for one chapter

        Args:
            chapter_info: Dict with chapter metadata
            chapters_dir: Directory with extracted chapters
            output_path: Where to save final video
        """
        print(f"\n  Rendering Chapter {chapter_info['number']}: {chapter_info['title']}")

        temp_dir = self.script_dir / "temp"
        temp_dir.mkdir(exist_ok=True)

        width = self.config["format"]["width"]
        height = self.config["format"]["height"]
        fps = self.config["format"]["fps"]

        # 1. Create intro card
        print("    Creating intro card...")
        intro_card = temp_dir / f"intro_{chapter_info['number']}.png"
        create_cards.create_intro_card(
            chapter_info['number'],
            chapter_info['title'],
            7,  # total chapters
            intro_card,
            brand_name=self.config["brand"]["name"]
        )

        # Convert intro card to video
        intro_video = temp_dir / f"intro_{chapter_info['number']}.mp4"
        intro_dur = self.config["intro"]["duration"]

        subprocess.run([
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(intro_card),
            "-c:v", "libx264", "-t", str(intro_dur),
            "-pix_fmt", "yuv420p", "-r", str(fps),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            str(intro_video)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print(f"    ✓ Intro card: {intro_dur}s")

        # 2. Prepare vertical background (simple black for now, can add waveform)
        print("    Creating background...")
        main_bg = temp_dir / f"bg_{chapter_info['number']}.mp4"
        duration = chapter_info['duration']

        # Create black background with waveform
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:d={duration}:r={fps}",
            "-i", chapter_info['audio_file'],
            "-filter_complex",
            f"[0:v][1:a]showwaves=s={width}x300:mode=line:rate={fps}:colors=#FFFFFF@0.3[wave];"
            f"[0:v][wave]overlay=(W-w)/2:(H-h)/2[out]",
            "-map", "[out]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(main_bg)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 3. Render animated captions (HyperFrames)
        print("    Rendering animated captions...")
        captions_video = temp_dir / f"captions_{chapter_info['number']}.mp4"
        self.render_caption_video(
            chapter_info['transcript_file'],
            captions_video,
            duration
        )

        # 4. Composite captions over background
        print("    Compositing layers...")
        main_content = temp_dir / f"main_{chapter_info['number']}.mp4"

        subprocess.run([
            "ffmpeg", "-y",
            "-i", str(main_bg),
            "-i", str(captions_video),
            "-i", chapter_info['audio_file'],
            "-filter_complex",
            "[0:v][1:v]overlay=0:0[video]",
            "-map", "[video]", "-map", "2:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            str(main_content)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print(f"    ✓ Main content: {duration:.1f}s")

        # 5. Create outro card
        print("    Creating outro card...")
        outro_card = temp_dir / f"outro_{chapter_info['number']}.png"
        create_cards.create_outro_card(
            outro_card,
            brand_handle=self.config["outro"]["handle"],
            cta_text=self.config["outro"]["cta_text"]
        )

        # Convert outro card to video
        outro_video = temp_dir / f"outro_{chapter_info['number']}.mp4"
        outro_dur = self.config["outro"]["duration"]

        subprocess.run([
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(outro_card),
            "-c:v", "libx264", "-t", str(outro_dur),
            "-pix_fmt", "yuv420p", "-r", str(fps),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            str(outro_video)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print(f"    ✓ Outro card: {outro_dur}s")

        # 6. Concatenate intro + main + outro
        print("    Concatenating segments...")
        concat_list = temp_dir / f"concat_{chapter_info['number']}.txt"
        with open(concat_list, 'w') as f:
            f.write(f"file '{intro_video}'\n")
            f.write(f"file '{main_content}'\n")
            f.write(f"file '{outro_video}'\n")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c", "copy",
            str(output_path)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        total_duration = intro_dur + duration + outro_dur
        print(f"    ✓ Final video: {output_path.name} ({total_duration:.1f}s)")

        return output_path

    def render_all_shorts(self, chapters_index_path, output_dir):
        """Render all chapter shorts"""
        with open(chapters_index_path) as f:
            chapters = json.load(f)

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"RENDERING {len(chapters)} SHORT-FORM VIDEOS")
        print(f"{'='*60}")

        rendered = []
        chapters_dir = Path(chapters_index_path).parent

        for chapter in chapters:
            output_path = output_dir / f"{chapter['filename_base']}.mp4"
            self.render_chapter_short(chapter, chapters_dir, output_path)
            rendered.append(str(output_path))

        print(f"\n{'='*60}")
        print(f"✓ COMPLETE! {len(rendered)} videos ready")
        print(f"{'='*60}\n")
        print(f"Output directory: {output_dir}")

        return rendered


def main():
    if len(sys.argv) < 2:
        print("Usage: render_shorts.py <chapters_index.json> [output_dir]")
        sys.exit(1)

    chapters_index = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./shorts/final"

    renderer = ShortsRenderer()
    renderer.render_all_shorts(chapters_index, output_dir)


if __name__ == "__main__":
    main()
