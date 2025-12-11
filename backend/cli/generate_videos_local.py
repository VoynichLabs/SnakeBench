#!/usr/bin/env python3
"""Local backfill tool to generate MP4 videos from Snake game replays.

This script is designed for the arc-explainer repo:
- It reads local replay JSON files (no Supabase access).
- It uses SnakeVideoGenerator.generate_video with replay_data provided.
- It writes MP4 files to a configured output directory.

Default assumptions:
- Input replay JSONs live under ../completed_games/ as snake_game_<game_id>.json.
- Output MP4s go under ../completed_games_videos/ with matching basenames.

Usage examples (from repo root with .venv activated):

    python external/SnakeBench/backend/cli/generate_videos_local.py \
        --root external/SnakeBench/backend/completed_games \
        --output-dir external/SnakeBench/backend/completed_games_videos

You can also limit the number processed or overwrite existing videos:

    python external/SnakeBench/backend/cli/generate_videos_local.py --limit 50 --overwrite
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List

# Ensure backend services are importable
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.video_generator import SnakeVideoGenerator  # type: ignore  # noqa: E402


logger = logging.getLogger(__name__)


def iter_replay_files(root: Path) -> List[Path]:
    """Return a sorted list of local replay JSON files."""
    return sorted(root.glob("snake_game_*.json"))


def extract_game_id(json_path: Path) -> str:
    """Extract game_id from filename like snake_game_<game_id>.json."""
    stem = json_path.stem
    if stem.startswith("snake_game_"):
        return stem[len("snake_game_") :]
    return stem


def load_replay(json_path: Path) -> Dict:
    """Load replay JSON from disk."""
    with json_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def process_replay(
    json_path: Path,
    output_dir: Path,
    generator: SnakeVideoGenerator,
    overwrite: bool = False,
) -> str:
    """Generate a video for a single replay JSON.

    Returns a status string: "ok", "skipped", or "failed".
    """
    game_id = extract_game_id(json_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{json_path.stem}.mp4"

    if output_path.exists() and not overwrite:
        logger.info("Skipping %s (video already exists)", json_path.name)
        return "skipped"

    try:
        replay_data = load_replay(json_path)
        logger.info("Generating video for %s (game_id=%s)", json_path.name, game_id)
        generator.generate_video(
            game_id=game_id,
            replay_data=replay_data,
            output_path=str(output_path),
        )
        logger.info("✓ Generated %s", output_path)
        return "ok"
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to generate video for %s: %s", json_path, exc)
        return "failed"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate local MP4 videos from Snake game replays (no Supabase)",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=str(BACKEND_ROOT / "completed_games"),
        help="Directory containing snake_game_*.json (default: ../completed_games)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(BACKEND_ROOT / "completed_games_videos"),
        help="Directory to write MP4 files (default: ../completed_games_videos)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional maximum number of replays to process (for testing)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate videos even if an output file already exists",
    )
    parser.add_argument(
        "--game-ids",
        type=str,
        help="Optional comma-separated list of game IDs to process (others will be ignored)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    root = Path(args.root).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Root directory does not exist or is not a directory: {root}")

    replay_files = iter_replay_files(root)

    # Optional filter: restrict to a specific set of game IDs
    if args.game_ids:
        wanted_ids = {gid.strip() for gid in args.game_ids.split(",") if gid.strip()}
        if wanted_ids:
            replay_files = [p for p in replay_files if extract_game_id(p) in wanted_ids]

    if args.limit is not None:
        replay_files = replay_files[: args.limit]

    if not replay_files:
        logger.info("No replay JSON files found under %s", root)
        return

    logger.info("Found %d replay files to process", len(replay_files))

    generator = SnakeVideoGenerator()

    counts = {"ok": 0, "skipped": 0, "failed": 0}

    for idx, json_path in enumerate(replay_files, start=1):
        logger.info("[%d/%d] Processing %s", idx, len(replay_files), json_path.name)
        status = process_replay(json_path, output_dir, generator, overwrite=args.overwrite)
        if status in counts:
            counts[status] += 1

    logger.info(
        "Done. ok=%d, skipped=%d, failed=%d",
        counts["ok"],
        counts["skipped"],
        counts["failed"],
    )


if __name__ == "__main__":
    main()
