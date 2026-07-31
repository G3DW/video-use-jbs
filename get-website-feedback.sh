#!/bin/bash
# Pull 17:20 - 43:29 of the AI Marketing Masterclass stream and transcribe it
# with ElevenLabs Scribe (diarized) using this repo's existing helper.
set -e

REPO="$(cd "$(dirname "$0")" && pwd)"
URL="https://www.youtube.com/watch?v=gTcOYO4rYbE"
START="00:17:20"
END="00:43:29"
WORK="$REPO/website-feedback"
mkdir -p "$WORK"

command -v yt-dlp  >/dev/null || { echo "ERROR: yt-dlp not on PATH"; exit 1; }
command -v ffmpeg  >/dev/null || { echo "ERROR: ffmpeg not on PATH"; exit 1; }
[ -x "$REPO/.venv/bin/python" ] || { echo "ERROR: no .venv in $REPO"; exit 1; }

# ---- 1. download ONLY the 17:20-43:29 audio window ----------------------
if [ ! -f "$WORK/segment.m4a" ]; then
  echo "==> Downloading audio for $START - $END ..."
  rm -f "$WORK"/raw.*
  if ! yt-dlp -f bestaudio --no-playlist \
        --download-sections "*${START}-${END}" \
        --force-keyframes-at-cuts \
        -o "$WORK/raw.%(ext)s" "$URL"; then
    echo "    section download failed, falling back to full audio + local trim"
    yt-dlp -f bestaudio --no-playlist -o "$WORK/raw.%(ext)s" "$URL"
  fi
  RAW=$(ls "$WORK"/raw.* | head -1)

  # normalize + guarantee exact bounds (harmless if already trimmed)
  DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$RAW" | cut -d. -f1)
  if [ "$DUR" -gt 1700 ]; then
    echo "==> Trimming to $START - $END ..."
    ffmpeg -y -loglevel error -i "$RAW" -ss "$START" -to "$END" -vn -c:a aac "$WORK/segment.m4a"
  else
    ffmpeg -y -loglevel error -i "$RAW" -vn -c:a aac "$WORK/segment.m4a"
  fi
  rm -f "$WORK"/raw.*
else
  echo "==> segment.m4a already exists, skipping download"
fi

# ---- 2. transcribe with ElevenLabs Scribe ------------------------------
echo "==> Transcribing with Scribe (~26 min of audio, diarized)..."
"$REPO/.venv/bin/python" "$REPO/helpers/transcribe.py" \
  "$WORK/segment.m4a" --edit-dir "$WORK" --language en

echo ""
echo "DONE -> $WORK/transcripts/segment.json"
echo "Timestamps inside it start at 0:00, which is 17:20 in the video."
