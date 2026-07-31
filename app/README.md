# video-use studio

Visual interface for the video-use pipeline. Everything that used to live only in a
Claude Code terminal session — transcript/takes view, proposed cuts with reasons,
timeline with preview, render progress, grade controls, subtitle styling, animation
slots, and the self-eval pass — in a browser, desktop and phone.

## Run it

```bash
cd video-use/app
npm install          # first time (re-run after switching machines/OS)
npm run dev          # → http://localhost:3123
```

Open the URL, pick your footage folder (recent + auto-discovered folders in the repo
show up as cards, or paste any absolute path), and the editor loads whatever exists
in its `edit/` directory. A fresh folder works too — use Transcribe → Pack from the
Pipeline console, then talk to the agent.

To use it from your phone on the same network: `npm run dev -- -H 0.0.0.0` and open
`http://<your-mac-ip>:3123`. Below 880px the UI switches to the TikTok-style layout
(filmstrip timeline, trim handles, bottom sheets).

## Requirements

- Node 20+ (22 recommended), `ffmpeg`/`ffprobe` on PATH
- Python env for the helpers — auto-detected from the repo `.venv`, or set `PYTHON_BIN`
- Agent chat uses the Claude Agent SDK with your existing local Claude Code
  credentials (`claude` login or `ANTHROPIC_API_KEY`)
- `ELEVENLABS_API_KEY` in the repo `.env` for transcription (unchanged from the skill)

### Env overrides (optional, `app/.env` or shell)

| var | purpose |
| --- | --- |
| `PYTHON_BIN` | python interpreter for helpers (default: repo `.venv`, else `python3`) |
| `FFMPEG_DIR` | prepended to PATH — point at an ffmpeg build with libass (e.g. homebrew `ffmpeg-full`) if the default one can't burn subtitles |
| `VIDEO_USE_ROOT` | repo root, if the app runs from outside `video-use/app` |

## How it maps to the skill

- **edl.json is the single source of truth.** The UI and the agent both edit it;
  every save keeps a restorable backup (History tab). Timeline drags snap to word
  boundaries with pad (Hard Rules 6+7).
- **Renders** call `helpers/render.py` unchanged (draft/preview/final), with live
  parsed progress. A "stale" badge appears when edl.json is newer than the render.
- **Subtitles** are built as a full standalone `master.ass` (style baked into
  V4+ Styles, not force_style — see Listaza Session 3) with output-timeline offsets
  (Hard Rule 5), wired into the EDL, burned LAST at render (Hard Rule 1). Style
  lives in `edit/studio_subs.json`.
- **Grade** previews any preset (or custom ffmpeg filter) on the selected segment's
  frame — original vs graded — then writes `edl.grade`. Baked per-segment at render.
- **Animations** are agent-authored (parallel sub-agents per slot, per the skill);
  the Animations tab lists slots, previews renders, and edits overlay placement.
- **Self-eval** is one button: the agent runs skill step 7 on the rendered output
  and its check images land in the Self-Eval tab from `edit/verify/`.
- **Agent chat** runs the same loop as the terminal (SKILL.md is the system prompt,
  cwd is your footage folder). Strategy proposals render as an Approve/Revise card
  (Hard Rule 11). Tool calls stream as a step console — no more scrolling blind.

## Deploying later (Vercel)

The frontend is deployable as-is, but transcription/ffmpeg/agent runs execute on
whatever machine hosts the API routes — serverless won't cut it. The intended split
is frontend on Vercel + this same Next server (or a Browser Use Box / VPS) running
`npm start` next to the footage. Until then, `npm run dev` on the editing machine is
the supported path.
