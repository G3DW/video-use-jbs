#!/usr/bin/env python3
"""Publish a local creative asset to Command Center's Viewscreen feed."""

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_MANIFEST = Path(
    "/Users/joey_makes_stuff/Documents/AgenticOS/CommandCenter/data/viewscreen-assets.json"
)
VALID_TYPES = {"cover", "slideshow-frame", "chart-export"}


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {"schemaVersion": 1, "assets": []}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[error] invalid Viewscreen manifest {path}: {exc}")
    if not isinstance(data.get("assets"), list):
        raise SystemExit(f"[error] invalid Viewscreen manifest {path}: assets must be a list")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="local image file to show")
    parser.add_argument("--type", required=True, choices=sorted(VALID_TYPES))
    parser.add_argument("--title", required=True, help="human-readable asset title")
    parser.add_argument("--agent", default="DAX", help="creator label shown in the Viewscreen")
    parser.add_argument("--caption", default="", help="optional short detail")
    parser.add_argument("--episode-date", default=None, help="YYYY-MM-DD when tied to an episode")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="override for testing")
    args = parser.parse_args()

    asset_path = Path(args.file).expanduser().resolve()
    if not asset_path.is_file() or asset_path.stat().st_size == 0:
        raise SystemExit(f"[error] asset not found or empty: {asset_path}")
    if asset_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        raise SystemExit("[error] Viewscreen assets must be JPG, PNG, WEBP, or GIF")

    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest = load_manifest(manifest_path)
    digest = hashlib.sha256(str(asset_path).encode()).hexdigest()[:10]
    asset_id = f"{args.type}-{digest}"
    asset = {
        "id": asset_id,
        "type": args.type,
        "title": args.title,
        "agent": args.agent,
        "caption": args.caption,
        "path": str(asset_path),
        "episodeDate": args.episode_date,
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    existing = [item for item in manifest["assets"] if item.get("id") != asset_id]
    manifest["assets"] = [asset, *existing][:50]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = manifest_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(manifest, indent=2) + "\n")
    os.replace(temp_path, manifest_path)
    print(f"[done] published {asset_id} to {manifest_path}")


if __name__ == "__main__":
    main()
