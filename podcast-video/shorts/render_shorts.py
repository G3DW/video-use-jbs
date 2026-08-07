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

# Shared icon library (generate_broll.py, one directory up) so shorts
# callouts reuse the same hand-drawn flat-icon glyphs as the horizontal
# video's icon-badge cards instead of a second, drifting icon set.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from generate_broll import ICON_LIBRARY


class ShortsRenderer:
    def __init__(self, config_path=None, background_image=None, logo_reveal_video=None):
        self.script_dir = Path(__file__).parent
        self.config = self.load_config(config_path)
        self.safe_zone = self.load_safe_zone()
        self.background_image = background_image
        self.logo_reveal_video = logo_reveal_video

    def load_safe_zone(self):
        """Load the cross-platform (TikTok ∩ Reels/Facebook) safe-zone margins"""
        safe_zones_path = self.script_dir / "safe_zones.json"
        with open(safe_zones_path) as f:
            return json.load(f)["cross_post_safe"]

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
                "duration": 2.0,
                "cta_text": "Full Episode Available",
                "handle": "@JoeBuildsSystems on YouTube",
                "wordmark": "The Daily AI Pulse Podcast"
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

    def render_overlay_composition(self, template_filename, duration, output_path, placeholders=None):
        """
        Render a safe-zone-aware HyperFrames overlay composition (captions,
        callouts, ...) to an alpha-capable mov.

        Args:
            template_filename: file under hyperframes_overlays/ (e.g. "captions.html")
            duration: composition duration in seconds
            output_path: where to save the rendered video (suffix forced to .mov)
            placeholders: extra {{KEY}}: value substitutions beyond DURATION/safe-zone/brand
        """
        overlays_dir = self.script_dir / "hyperframes_overlays"
        template_path = overlays_dir / template_filename
        with open(template_path) as f:
            html_content = f.read()

        # Inline safe-zone.css (own placeholders substituted) and brand.css
        # so the rendered composition doesn't depend on separate temp files
        css_path = overlays_dir / "safe-zone.css"
        with open(css_path) as f:
            css_content = f.read()
        css_content = (
            css_content
            .replace("{{SAFE_TOP}}", str(self.safe_zone["top"]))
            .replace("{{SAFE_BOTTOM}}", str(self.safe_zone["bottom"]))
            .replace("{{SAFE_LEFT}}", str(self.safe_zone["left"]))
            .replace("{{SAFE_RIGHT}}", str(self.safe_zone["right"]))
        )
        html_content = html_content.replace(
            '<link rel="stylesheet" href="safe-zone.css">',
            f"<style>{css_content}</style>"
        )

        brand_css_path = overlays_dir / "brand.css"
        if brand_css_path.exists():
            with open(brand_css_path) as f:
                brand_css_content = f.read()
            html_content = html_content.replace(
                '<link rel="stylesheet" href="brand.css">',
                f"<style>{brand_css_content}</style>"
            )

        html_content = html_content.replace("{{DURATION}}", str(duration))
        for key, value in (placeholders or {}).items():
            html_content = html_content.replace("{{" + key + "}}", value)

        # Write the composition as index.html so `hyperframes render <dir>`
        # picks it up by default (no -c flag needed)
        composition_html = overlays_dir / "index.html"
        with open(composition_html, 'w') as f:
            f.write(html_content)

        # Render with HyperFrames. Duration/fps/dimensions come from the
        # composition root's data-* attributes (current CLI has no
        # --width/--height/--duration flags). Request mov (ProRes 4444) so
        # the alpha channel survives for the overlay compositing step below
        # — webm (vp9) came back as opaque yuv420p in testing, mov came
        # back as real yuva444p12le.
        print(f"    Rendering {template_filename} with HyperFrames...")

        fps = self.config["format"]["fps"]
        output_path = Path(output_path).with_suffix(".mov")

        cmd = [
            "npx", "--yes", "hyperframes", "render",
            str(overlays_dir),
            "-o", str(output_path),
            "--fps", str(fps),
            "--format", "mov",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"    ✗ HyperFrames render failed ({template_filename}): {result.stderr}")
            # Fallback: create transparent video with ffmpeg
            return self.create_transparent_placeholder(output_path, duration)

        print(f"    ✓ Rendered: {output_path}")
        return output_path

    def load_words(self, transcript_file, offset=0):
        """Load word-level timing from a chapter transcript, shifted by
        `offset` seconds (used when a chapter's caption/callout section no
        longer starts at t=0, e.g. after an intro segment). Words that end
        before the offset (fully covered by the intro) are dropped."""
        with open(transcript_file) as f:
            data = json.load(f)

        words = [w for w in data.get('words', []) if w.get('type') != 'spacing']

        shifted = []
        for word in words:
            start = word.get('start', 0) - offset
            end = word.get('end', 0) - offset
            if end <= 0:
                continue
            shifted.append({
                "text": word.get('text', '').strip(),
                "start": max(0, start),
                "end": end
            })
        return shifted

    def load_callouts(self, callouts_file, offset=0):
        """Load story-callout data (icon+text chips), shifted the same way
        as load_words. Returns [] if no callouts file exists for this
        chapter — callouts are optional, hand-authored per chapter. The
        `icon` field is a key into ICON_LIBRARY (shared with
        generate_broll.py), resolved here to inline SVG markup."""
        callouts_file = Path(callouts_file)
        if not callouts_file.exists():
            return []

        with open(callouts_file) as f:
            callouts = json.load(f)

        shifted = []
        for c in callouts:
            start = c.get('start', 0) - offset
            end = c.get('end', 0) - offset
            if end <= 0:
                continue
            icon_key = c.get('icon', '')
            shifted.append({
                "text": c.get('text', ''),
                "icon": ICON_LIBRARY.get(icon_key, ''),
                "accent": c.get('accent', ''),
                "start": max(0, start),
                "end": end
            })
        return shifted

    def create_transparent_placeholder(self, output_path, duration):
        """Create transparent video as fallback (matches the alpha-capable
        mov the successful HyperFrames render path produces)"""
        width = self.config["format"]["width"]
        height = self.config["format"]["height"]
        fps = self.config["format"]["fps"]
        output_path = Path(output_path).with_suffix(".mov")

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i",
            f"color=c=black@0.0:s={width}x{height}:d={duration}:r={fps}",
            "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
            str(output_path)
        ]

        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_path

    def render_chapter_short(self, chapter_info, chapters_dir, output_path, total_chapters=7):
        """
        Render complete short-form video for one chapter

        Args:
            chapter_info: Dict with chapter metadata
            chapters_dir: Directory with extracted chapters
            output_path: Where to save final video
            total_chapters: Total chapter count shown on the intro card
                ("Chapter N of <total_chapters>") — pass len(chapters_index)
                rather than assuming a fixed 7-chapter batch.
        """
        print(f"\n  Rendering Chapter {chapter_info['number']}: {chapter_info['title']}")

        n = chapter_info['number']
        temp_dir = self.script_dir / "temp"
        temp_dir.mkdir(exist_ok=True)
        overlays_dir = self.script_dir / "hyperframes_overlays"

        width = self.config["format"]["width"]
        height = self.config["format"]["height"]
        fps = self.config["format"]["fps"]
        audio_args = ["-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k"]

        chapter_duration = chapter_info['duration']
        intro_dur = min(self.config["intro"]["duration"], chapter_duration - 1)
        main_dur = chapter_duration - intro_dur

        # 1. Intro segment — trimmed logo-reveal video, its own sting mixed
        # with the chapter narration starting immediately (no dead air
        # waiting for the logo to finish; captions pick up once segment 2
        # starts, so the words spoken during the intro are heard but not
        # captioned — a normal cold-open pattern for shorts).
        print("    Creating intro (logo reveal + narration)...")
        intro_video = temp_dir / f"intro_{n}.mp4"

        if self.logo_reveal_video:
            subprocess.run([
                "ffmpeg", "-y",
                "-i", str(self.logo_reveal_video),
                "-i", chapter_info['audio_file'],
                "-filter_complex",
                f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},fps={fps}[v];"
                f"[0:a]atrim=0:{intro_dur},asetpts=PTS-STARTPTS,volume=0.7[sting];"
                f"[1:a]atrim=0:{intro_dur},asetpts=PTS-STARTPTS[narr];"
                f"[sting][narr]amix=inputs=2:duration=first:dropout_transition=0,volume=2[a]",
                "-map", "[v]", "-map", "[a]",
                "-t", str(intro_dur),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", *audio_args,
                str(intro_video)
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # Fallback: static PIL intro card (no logo-reveal video supplied)
            intro_card = temp_dir / f"intro_{n}.png"
            create_cards.create_intro_card(
                n, chapter_info['title'], total_chapters, intro_card,
                brand_name=self.config["brand"]["name"]
            )
            subprocess.run([
                "ffmpeg", "-y",
                "-loop", "1", "-i", str(intro_card),
                "-i", chapter_info['audio_file'],
                "-filter_complex", f"[1:a]atrim=0:{intro_dur},asetpts=PTS-STARTPTS[a]",
                "-map", "0:v", "-map", "[a]",
                "-c:v", "libx264", "-t", str(intro_dur),
                "-pix_fmt", "yuv420p", "-r", str(fps),
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
                *audio_args,
                str(intro_video)
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print(f"    ✓ Intro: {intro_dur:.1f}s")

        # 2. Remaining narration for the main (captioned) section
        main_narration = temp_dir / f"main_narration_{n}.m4a"
        subprocess.run([
            "ffmpeg", "-y",
            "-i", chapter_info['audio_file'],
            "-ss", str(intro_dur),
            *audio_args,
            str(main_narration)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 3. Prepare vertical background (solid black, or a static image if
        # one was supplied — e.g. when there's no correctly-sized source
        # video available yet) with a waveform overlay
        print("    Creating background...")
        main_bg = temp_dir / f"bg_{n}.mp4"

        if self.background_image:
            bg_input = [
                "-loop", "1", "-t", str(main_dur), "-i", str(self.background_image)
            ]
            bg_video_filter = f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}[bg];"
        else:
            bg_input = [
                "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:d={main_dur}:r={fps}"
            ]
            bg_video_filter = "[0:v]copy[bg];"

        subprocess.run([
            "ffmpeg", "-y",
            *bg_input,
            "-i", str(main_narration),
            "-filter_complex",
            f"{bg_video_filter}"
            f"[1:a]showwaves=s={width}x300:mode=line:rate={fps}:colors=#FFFFFF@0.3[wave];"
            f"[bg][wave]overlay=(W-w)/2:(H-h)/2[out]",
            "-map", "[out]",
            "-r", str(fps),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(main_bg)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 4. Render animated captions + story callouts (HyperFrames,
        # mov/ProRes4444 w/ alpha), both timed relative to the main section
        # (i.e. shifted back by intro_dur from their chapter-relative times)
        print("    Rendering animated captions...")
        word_data = self.load_words(chapter_info['transcript_file'], offset=intro_dur)
        captions_video = self.render_overlay_composition(
            "captions.html", main_dur, temp_dir / f"captions_{n}.mov",
            placeholders={"WORDS_DATA": json.dumps(word_data)}
        )

        print("    Rendering story callouts...")
        callouts_path = Path(chapter_info['transcript_file']).with_name(
            Path(chapter_info['transcript_file']).name.replace("-transcript.json", "-callouts.json")
        )
        callout_data = self.load_callouts(callouts_path, offset=intro_dur)
        callouts_video = self.render_overlay_composition(
            "callouts.html", main_dur, temp_dir / f"callouts_{n}.mov",
            placeholders={"CALLOUTS_DATA": json.dumps(callout_data)}
        )

        # 5. Composite captions + callouts over background (alpha-blends
        # automatically since both overlay layers carry an alpha channel)
        print("    Compositing layers...")
        main_content = temp_dir / f"main_{n}.mp4"

        subprocess.run([
            "ffmpeg", "-y",
            "-i", str(main_bg),
            "-i", str(captions_video),
            "-i", str(callouts_video),
            "-i", str(main_narration),
            "-filter_complex",
            "[0:v][1:v]overlay=0:0[v1];[v1][2:v]overlay=0:0[video]",
            "-map", "[video]", "-map", "3:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            *audio_args,
            str(main_content)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print(f"    ✓ Main content: {main_dur:.1f}s")

        # 6. Outro CTA card — safe-zone-bound HyperFrames composition over
        # the same background image, styled to match the horizontal video's
        # outro card. No more narration exists past the chapter's natural
        # end, so this segment carries a silent (but present, for concat
        # stream consistency) audio track rather than faked continuation.
        print("    Rendering outro CTA card...")
        outro_dur = self.config["outro"]["duration"]

        if self.background_image:
            shutil.copy(self.background_image, overlays_dir / "bg-image.png")

        outro_mov = self.render_overlay_composition(
            "outro-card.html", outro_dur, temp_dir / f"outro_{n}.mov",
            placeholders={
                "WORDMARK": self.config["outro"]["wordmark"],
                "TAGLINE": self.config["outro"]["cta_text"],
                "HANDLE": self.config["outro"]["handle"],
            }
        )

        outro_video = temp_dir / f"outro_{n}.mp4"
        subprocess.run([
            "ffmpeg", "-y",
            "-i", str(outro_mov),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-t", str(outro_dur),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", *audio_args,
            "-shortest",
            str(outro_video)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print(f"    ✓ Outro card: {outro_dur:.1f}s")

        # 7. Concatenate intro + main + outro (all now share codec/audio
        # format so concat demuxer -c copy carries audio through cleanly)
        print("    Concatenating segments...")
        concat_list = temp_dir / f"concat_{n}.txt"
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

        total_duration = intro_dur + main_dur + outro_dur
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
            self.render_chapter_short(chapter, chapters_dir, output_path, total_chapters=len(chapters))
            rendered.append(str(output_path))

        print(f"\n{'='*60}")
        print(f"✓ COMPLETE! {len(rendered)} videos ready")
        print(f"{'='*60}\n")
        print(f"Output directory: {output_dir}")

        return rendered


def main():
    if len(sys.argv) < 2:
        print("Usage: render_shorts.py <chapters_index.json> [output_dir] "
              "[--background-image PATH] [--logo-reveal-video PATH]")
        sys.exit(1)

    args = sys.argv[1:]
    background_image = None
    if "--background-image" in args:
        idx = args.index("--background-image")
        background_image = args[idx + 1]
        del args[idx:idx + 2]

    logo_reveal_video = None
    if "--logo-reveal-video" in args:
        idx = args.index("--logo-reveal-video")
        logo_reveal_video = args[idx + 1]
        del args[idx:idx + 2]

    chapters_index = args[0]
    output_dir = args[1] if len(args) > 1 else "./shorts/final"

    renderer = ShortsRenderer(background_image=background_image, logo_reveal_video=logo_reveal_video)
    renderer.render_all_shorts(chapters_index, output_dir)


if __name__ == "__main__":
    main()
