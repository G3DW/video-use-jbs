#!/usr/bin/env python3
"""
AI Scene Generator for Blotato
Converts podcast transcript into visually rich AI-generated animated scenes
"""

import json
import os
import time
import requests
from pathlib import Path
from typing import List, Dict, Any


def _load_env_file(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE per line, strips surrounding quotes.
    Does not overwrite variables already present in the environment."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ.setdefault(key, value)


# Known-valid values for the "AI Video with AI Voice" template, pulled from
# GET /v2/videos/templates?fields=id,inputs on 2026-07-24.
VALID_AI_IMAGE_MODELS = [
    "replicate/black-forest-labs/flux-schnell",
    "replicate/black-forest-labs/flux-dev",
    "replicate/black-forest-labs/flux-1.1-pro",
    "replicate/black-forest-labs/flux-1.1-pro-ultra",
    "replicate/recraft-ai/recraft-v3",
    "replicate/ideogram-ai/ideogram-v2",
    "replicate/luma/photon",
    "openai/gpt-image-1",
    "fal-ai/nano-banana",
    "fal-ai/nano-banana-2",
    "fal-ai/nano-banana-pro",
    "fal-ai/imagen4/preview/fast",
    "fal-ai/bytedance/seedream/v4.5/text-to-image",
]

VALID_ASPECT_RATIOS = ["16:9", "1:1", "4:5", "9:16"]
VALID_TRANSITIONS = ["none", "fade", "slide", "zoom"]
VALID_CAPTION_POSITIONS = ["top", "center", "bottom"]

MAX_SCENES = 20

# Statuses reported by GET /v2/videos/creations/:id
IN_PROGRESS_STATUSES = {
    "queueing", "generating-script", "script-ready",
    "generating-media", "media-ready", "exporting",
}
DONE_STATUS = "done"
FAILED_STATUSES = {"creation-from-template-failed", "failed", "error"}


class AISceneGenerator:
    """Generate AI-powered visual scenes using Blotato API"""

    def __init__(self, api_key: str = None):
        # Load ~/.claude/skills/podcast-video/.env (one level up from this file)
        _load_env_file(Path(__file__).resolve().parent.parent / '.env')

        self.api_key = api_key or os.getenv('BLOTATO_API_KEY')
        if not self.api_key:
            raise ValueError("BLOTATO_API_KEY not found in environment")

        self.base_url = "https://backend.blotato.com/v2"
        self.headers = {
            "Content-Type": "application/json",
            "blotato-api-key": self.api_key
        }

        # "AI Video with AI Voice" template. Must be the full template path,
        # not just the trailing UUID.
        self.template_id = "/base/v2/ai-story-video/5903fe43-514d-40ee-a060-0d6628c5f8fd/v1"

    def segment_transcript_into_scenes(self, transcript_data: Dict, max_scene_duration: float = 8.0,
                                        max_scenes: int = MAX_SCENES) -> List[Dict]:
        """
        Break transcript into semantic scenes of ~5-8 seconds each, then merge
        down to at most `max_scenes` (Blotato's hard cap) so the whole chapter
        stays covered rather than being truncated.

        Args:
            transcript_data: Scribe JSON with word-level timestamps
            max_scene_duration: Max seconds per scene
            max_scenes: Hard cap on scene count (Blotato max is 20)

        Returns:
            List of scenes with text, start/end times
        """
        words = [w for w in transcript_data.get('words', []) if w.get('type') != 'spacing']
        if not words:
            return []

        scenes = []

        current_scene = {
            'start': words[0]['start'],
            'words': [],
            'text': ''
        }

        for i, word in enumerate(words):
            current_scene['words'].append(word)

            # Calculate current scene duration
            duration = word['end'] - current_scene['start']

            # Break on: duration limit, sentence end, or significant pause
            is_sentence_end = word.get('text', '').strip().endswith(('.', '!', '?'))
            next_pause = (i < len(words) - 1 and
                         words[i + 1]['start'] - word['end'] > 0.8)

            if duration >= max_scene_duration or (duration >= 4.0 and (is_sentence_end or next_pause)):
                # Finalize current scene
                current_scene['end'] = word['end']
                current_scene['text'] = ' '.join([w.get('text', '').strip()
                                                  for w in current_scene['words']
                                                  if w.get('text', '').strip()])
                current_scene['duration'] = current_scene['end'] - current_scene['start']
                scenes.append(current_scene)

                # Start new scene (or, if this was the last word, mark that
                # there's no dangling scene left to finalize below — without
                # this, the same dict gets appended a second time when the
                # break condition fires exactly on the final word)
                if i < len(words) - 1:
                    current_scene = {
                        'start': words[i + 1]['start'],
                        'words': [],
                        'text': ''
                    }
                else:
                    current_scene = None

        # Add final scene (only if the loop didn't already finalize one
        # ending on the last word)
        if current_scene is not None and current_scene['words']:
            current_scene['end'] = words[-1]['end']
            current_scene['text'] = ' '.join([w.get('text', '').strip()
                                              for w in current_scene['words']
                                              if w.get('text', '').strip()])
            current_scene['duration'] = current_scene['end'] - current_scene['start']
            scenes.append(current_scene)

        # Drop the intermediate 'words' list now that text/duration are set
        for scene in scenes:
            scene.pop('words', None)

        return self.merge_scenes_to_limit(scenes, max_scenes)

    def merge_scenes_to_limit(self, scenes: List[Dict], limit: int = MAX_SCENES) -> List[Dict]:
        """
        Merge the shortest-duration scene into its shorter-duration neighbor,
        repeatedly, until len(scenes) <= limit. Preserves full time coverage
        (no scene is dropped) instead of truncating the tail.
        """
        scenes = [dict(s) for s in scenes]  # shallow copy, don't mutate caller's list

        while len(scenes) > limit:
            # Find index of shortest scene
            shortest_idx = min(range(len(scenes)), key=lambda i: scenes[i]['duration'])

            # Decide which neighbor to merge into (prefer the shorter neighbor;
            # fall back to the only available side at the ends)
            left_idx = shortest_idx - 1 if shortest_idx > 0 else None
            right_idx = shortest_idx + 1 if shortest_idx < len(scenes) - 1 else None

            if left_idx is None:
                merge_idx = right_idx
            elif right_idx is None:
                merge_idx = left_idx
            else:
                merge_idx = left_idx if scenes[left_idx]['duration'] <= scenes[right_idx]['duration'] else right_idx

            a, b = sorted([shortest_idx, merge_idx])
            merged = {
                'start': scenes[a]['start'],
                'end': scenes[b]['end'],
                'text': (scenes[a]['text'] + ' ' + scenes[b]['text']).strip(),
            }
            merged['duration'] = merged['end'] - merged['start']

            scenes[a:b + 1] = [merged]

        return scenes

    def generate_visual_prompts(self, scenes: List[Dict], chapter_context: str,
                               visual_style: str = "cinematic") -> List[Dict]:
        """
        Generate detailed visual prompts for each scene using Claude.

        NOTE: requires the `anthropic` package and ANTHROPIC_API_KEY to be set
        (billed separately from a Claude Code subscription). The recommended
        pipeline instead uses prepare_scenes.py to emit empty visual_prompt
        fields, which get filled in-session, then submit_short.py to submit.
        This method is kept for callers that do want the fully-automatic path.

        Args:
            scenes: List of scene dicts with text
            chapter_context: Overall chapter theme/topic
            visual_style: Visual aesthetic direction

        Returns:
            Scenes with added 'visual_prompt' field
        """
        import anthropic

        client = anthropic.Anthropic()

        # Build prompt for Claude
        scene_texts = [f"{i+1}. \"{s['text']}\" ({s['duration']:.1f}s)"
                      for i, s in enumerate(scenes)]

        system_prompt = f"""You are a visual director creating prompts for AI image generation.

Chapter context: {chapter_context}
Visual style: {visual_style}

For each scene of narration, create a detailed image generation prompt that:
1. Visually represents the concept being discussed
2. Matches the {visual_style} aesthetic
3. Works well for image-to-video animation
4. Avoids text/words in the image
5. Is 1-2 sentences, specific and vivid

Return ONLY a JSON array of objects with "scene_number" and "visual_prompt" fields."""

        user_prompt = f"""Create visual prompts for these {len(scenes)} scenes:

{chr(10).join(scene_texts)}

Return JSON array only, no other text."""

        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        # Parse response
        response_text = response.content[0].text.strip()
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]

        visual_prompts = json.loads(response_text)

        # Add visual prompts to scenes
        for i, scene in enumerate(scenes):
            matching = next((p for p in visual_prompts if p['scene_number'] == i + 1), None)
            if matching:
                scene['visual_prompt'] = matching['visual_prompt']
            else:
                # Fallback
                scene['visual_prompt'] = f"{visual_style} scene: {scene['text'][:100]}"

        return scenes

    def create_video(self, scenes: List[Dict],
                    ai_image_model: str = "replicate/black-forest-labs/flux-1.1-pro",
                    animate_images: bool = True,
                    aspect_ratio: str = "9:16",
                    title: str = "AI Generated Short",
                    enable_voiceover: bool = True,
                    voice_name: str = "Brian (American, deep)",
                    caption_position: str = "bottom",
                    transition: str = "none",
                    trim_to_voiceover: bool = True) -> Dict:
        """
        Submit video generation job to Blotato

        Args:
            scenes: List with 'visual_prompt' and 'text' for each scene
            ai_image_model: Which AI model to use for images (must be a valid
                Blotato model id, see VALID_AI_IMAGE_MODELS)
            animate_images: Convert images to animated video
            aspect_ratio: Output format
            title: Video title
            enable_voiceover: Generate an AI (ElevenLabs) voiceover
            voice_name: Which ElevenLabs voice to use
            caption_position: Where to burn captions (top/center/bottom).
                Note: this template always burns captions; there is no
                disable option.
            transition: Transition effect between scenes
            trim_to_voiceover: Trim each scene's video to match its voiceover

        Returns:
            The 'item' object from the creation response (contains 'id')
        """
        if ai_image_model not in VALID_AI_IMAGE_MODELS:
            raise ValueError(
                f"Invalid aiImageModel {ai_image_model!r}. Valid values: {VALID_AI_IMAGE_MODELS}"
            )
        if aspect_ratio not in VALID_ASPECT_RATIOS:
            raise ValueError(f"Invalid aspectRatio {aspect_ratio!r}. Valid values: {VALID_ASPECT_RATIOS}")
        if transition not in VALID_TRANSITIONS:
            raise ValueError(f"Invalid transition {transition!r}. Valid values: {VALID_TRANSITIONS}")
        if caption_position not in VALID_CAPTION_POSITIONS:
            raise ValueError(f"Invalid captionPosition {caption_position!r}. Valid values: {VALID_CAPTION_POSITIONS}")

        missing_prompts = [i for i, s in enumerate(scenes) if not s.get('visual_prompt')]
        if missing_prompts:
            raise ValueError(f"Scenes missing visual_prompt at indices: {missing_prompts}")

        if len(scenes) > MAX_SCENES:
            raise ValueError(
                f"{len(scenes)} scenes exceeds Blotato's max of {MAX_SCENES}. "
                f"Call merge_scenes_to_limit() before submitting."
            )

        # Format scenes for Blotato API
        blotato_scenes = [
            {"mediaSource": scene['visual_prompt'], "script": scene['text']}
            for scene in scenes
        ]

        payload = {
            "templateId": self.template_id,
            "title": title,
            "render": True,
            "inputs": {
                "scenes": blotato_scenes,
                "aiImageModel": ai_image_model,
                "animateAiImages": animate_images,
                "aspectRatio": aspect_ratio,
                "enableVoiceover": enable_voiceover,
                "voiceName": voice_name,
                "captionPosition": caption_position,
                "transition": transition,
                "trimToVoiceover": trim_to_voiceover,
            }
        }

        print(f"\nSubmitting to Blotato:")
        print(f"  Scenes: {len(blotato_scenes)}")
        print(f"  Model: {ai_image_model}")
        print(f"  Animated: {animate_images}")
        print(f"  Aspect: {aspect_ratio}")
        print(f"  Voiceover: {enable_voiceover} ({voice_name})")

        response = requests.post(
            f"{self.base_url}/videos/from-templates",
            headers=self.headers,
            json=payload
        )

        if not response.ok:
            print(f"Error response: {response.text}")
            response.raise_for_status()

        data = response.json()
        return data.get('item', data)

    def poll_status(self, creation_id: str, timeout: int = 1800) -> Dict:
        """
        Poll generation status until complete

        Args:
            creation_id: Job ID from create_video
            timeout: Max seconds to wait

        Returns:
            Final 'item' object with mediaUrl
        """
        start_time = time.time()
        last_status = None

        while time.time() - start_time < timeout:
            response = requests.get(
                f"{self.base_url}/videos/creations/{creation_id}",
                headers=self.headers
            )

            if not response.ok:
                print(f"Error checking status: {response.text}")
                response.raise_for_status()

            data = response.json()
            item = data.get('item', data)
            status = item.get('status')

            if status != last_status:
                print(f"Status: {status}")
                if status is not None and status not in IN_PROGRESS_STATUSES and status != DONE_STATUS and status not in FAILED_STATUSES:
                    print(f"  (unrecognized status, continuing to poll: {status!r})")
                last_status = status

            if status == DONE_STATUS:
                return item
            elif status in FAILED_STATUSES:
                raise RuntimeError(f"Generation failed: {item.get('error', item)}")

            time.sleep(10)

        raise TimeoutError(f"Generation timed out after {timeout}s")

    def download_video(self, media_url: str, output_path: Path) -> Path:
        """Download generated video"""
        print(f"\nDownloading: {media_url}")

        response = requests.get(media_url, stream=True)
        response.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"✓ Saved: {output_path} ({output_path.stat().st_size / 1_000_000:.1f} MB)")
        return output_path


if __name__ == "__main__":
    # Example usage
    print("AI Scene Generator initialized")
    print("Use this module to create visually rich AI-generated shorts")
