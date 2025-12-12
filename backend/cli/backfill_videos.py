#!/usr/bin/env python3
"""
One-off helper to backfill missing match videos.

- Scans local completed_games directory for replay JSON files
- Skips games that already have a video file (unless --force)
- Generates videos and saves them locally
- Runs work in parallel (default 4 workers)
"""

import argparse
import logging
import os
import sys
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

from dotenv import load_dotenv

# Add backend directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from services.video_generator import SnakeVideoGenerator

logger = logging.getLogger(__name__)
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_local_game_ids(limit: int | None = None, offset: int = 0) -> List[str]:
    """Find game IDs from local completed_games directory."""
    completed_games_dir = os.path.join(backend_path, "completed_games")
    pattern = os.path.join(completed_games_dir, "snake_game_*.json")
    
    all_files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    
    game_ids: List[str] = []
    for filepath in all_files:
        filename = os.path.basename(filepath)
        # Extract game ID from snake_game_<game_id>.json
        if filename.startswith("snake_game_") and filename.endswith(".json"):
            game_id = filename[11:-5]  # Remove "snake_game_" prefix and ".json" suffix
            game_ids.append(game_id)
    
    # Apply offset and limit
    game_ids = game_ids[offset:]
    if limit is not None:
        game_ids = game_ids[:limit]
    
    return game_ids


def video_exists_locally(game_id: str) -> bool:
    """Check whether video file already exists locally."""
    video_path = os.path.join(backend_path, "completed_games", f"{game_id}_replay.mp4")
    return os.path.exists(video_path)


def process_game(game_id: str, output_dir: str, force: bool = False) -> str:
    """Generate a video for a single game and save locally."""
    if video_exists_locally(game_id) and not force:
        logger.info("%s: video already exists, skipping", game_id)
        return "skipped_existing"

    try:
        generator = SnakeVideoGenerator()
        output_path = os.path.join(output_dir, f"{game_id}_replay.mp4")
        video_path = generator.generate_video(game_id, output_path=output_path)
        logger.info("%s: generated %s", game_id, video_path)
        return "generated"
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("%s: failed to generate (%s)", game_id, exc)
        return "failed"


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Backfill missing replay videos for local games")
    parser.add_argument(
        "--limit",
        type=int,
        help="Only process the first N games (default: all)",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Start processing from this offset",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even if video already exists locally",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Output directory for videos (default: completed_games)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    output_dir = args.output_dir or os.path.join(backend_path, "completed_games")
    os.makedirs(output_dir, exist_ok=True)
    logger.info("Output directory: %s", output_dir)

    game_ids = find_local_game_ids(limit=args.limit, offset=args.offset)
    if not game_ids:
        logger.info("No games found to process")
        return

    logger.info("Processing %s games with %s workers...", len(game_ids), args.workers)

    results_counter: Dict[str, int] = {
        "generated": 0,
        "skipped_existing": 0,
        "failed": 0,
    }

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_game = {
            executor.submit(process_game, game_id, output_dir, args.force): game_id
            for game_id in game_ids
        }

        for future in as_completed(future_to_game):
            status = future.result()
            if status in results_counter:
                results_counter[status] += 1

    logger.info(
        "Finished! Generated=%s, Skipped(existing)=%s, Failed=%s",
        results_counter["generated"],
        results_counter["skipped_existing"],
        results_counter["failed"],
    )


if __name__ == "__main__":
    main()
