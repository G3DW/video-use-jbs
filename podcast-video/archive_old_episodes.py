#!/usr/bin/env python3
"""
Daily archive job for JoeBuildsSystems podcast episodes.

Scans Content/<YYYY-MM-DD>-podcast folders. Any folder whose date is 2+
calendar days old gets copied to the local Google Drive sync path (the
Drive desktop app then syncs it to the cloud on its own), verified, and
then deleted locally to reclaim disk space.

Safe to run daily via launchd/cron — already-archived folders are skipped,
and nothing is deleted locally until the copy in the Drive folder is
verified to match (same file count and total size).
"""

import argparse
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

CONTENT_DIR = Path(
    "/Users/joey_makes_stuff/Documents/AgenticOS/JoeBuildsSystems/Content"
)
ARCHIVE_DIR = Path(
    "/Users/joey_makes_stuff/Library/CloudStorage/"
    "GoogleDrive-joe@astranexventures.com/My Drive/JBS Daily AI Pulse/Archive"
)
LOG_PATH = Path("/Users/joey_makes_stuff/.claude/skills/podcast-video/archive.log")
MIN_AGE_DAYS = 2

FOLDER_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-podcast$")


def log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line)
    with LOG_PATH.open("a") as f:
        f.write(line + "\n")


def folder_stats(path: Path) -> tuple[int, int]:
    """Return (file_count, total_bytes) for a directory tree."""
    file_count = 0
    total_bytes = 0
    for p in path.rglob("*"):
        if p.is_file():
            file_count += 1
            total_bytes += p.stat().st_size
    return file_count, total_bytes


def archive_one(episode_dir: Path, dry_run: bool) -> None:
    dest = ARCHIVE_DIR / episode_dir.name

    if dest.exists():
        log(f"SKIP {episode_dir.name}: already present at {dest}")
        return

    src_files, src_bytes = folder_stats(episode_dir)
    log(
        f"ARCHIVING {episode_dir.name}: {src_files} files, "
        f"{src_bytes / 1e6:.1f} MB -> {dest}"
    )

    if dry_run:
        log(f"DRY RUN: would copy then delete {episode_dir}")
        return

    shutil.copytree(episode_dir, dest)

    dest_files, dest_bytes = folder_stats(dest)
    if dest_files != src_files or dest_bytes != src_bytes:
        log(
            f"ERROR verifying copy of {episode_dir.name}: "
            f"src={src_files} files/{src_bytes}B, dest={dest_files} files/{dest_bytes}B "
            "-- leaving local copy in place, NOT deleting source."
        )
        return

    shutil.rmtree(episode_dir)
    log(f"DONE {episode_dir.name}: verified copy, deleted local source")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not CONTENT_DIR.is_dir():
        log(f"ERROR: content dir not found: {CONTENT_DIR}")
        return 1

    if not ARCHIVE_DIR.parent.is_dir():
        log(
            f"ERROR: Google Drive archive path not reachable: {ARCHIVE_DIR} "
            "(is the Drive desktop app running / signed in?)"
        )
        return 1

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    today = date.today()
    candidates = []
    for entry in sorted(CONTENT_DIR.iterdir()):
        if not entry.is_dir():
            continue
        m = FOLDER_RE.match(entry.name)
        if not m:
            continue
        try:
            folder_date = date.fromisoformat(m.group(1))
        except ValueError:
            continue
        age_days = (today - folder_date).days
        if age_days >= MIN_AGE_DAYS:
            candidates.append(entry)

    if not candidates:
        log("No episode folders old enough to archive.")
        return 0

    for episode_dir in candidates:
        archive_one(episode_dir, args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
