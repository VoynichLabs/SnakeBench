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


def fetch_game_ids(limit: int | None = None, offset: int = 0, batch_size: int = 500) -> List[str]:
    """Stream game IDs from Postgres in batches to avoid loading everything at once."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        game_ids: List[str] = []
        fetched = 0
        current_offset = offset

        while True:
            if limit is not None:
                # Clamp batch size to remaining requested rows
                remaining = limit - fetched
                if remaining <= 0:
                    break
                batch_take = min(batch_size, remaining)
            else:
                batch_take = batch_size

            cursor.execute(
                """
                SELECT id
                FROM games
                ORDER BY start_time DESC
                LIMIT %s OFFSET %s
                """,
                (batch_take, current_offset)
            )
            rows = cursor.fetchall()
            if not rows:
                break

            game_ids.extend(row["id"] for row in rows)
            fetched += len(rows)
            current_offset += batch_take

        return game_ids
    finally:
        cursor.close()
        conn.close()


def list_game_files(bucket: str, game_id: str) -> List[Dict]:
    """List files for a game folder in Supabase Storage."""
    supabase = get_supabase_client()
    try:
        return supabase.storage.from_(bucket).list(path=game_id)
    except Exception as exc:
        logger.warning("Could not list storage files for %s: %s", game_id, exc)
        return []


def video_exists(files: Iterable[Dict]) -> bool:
    """Check whether replay.mp4 is already present."""
    return any(file.get("name") == "replay.mp4" for file in files)


def replay_exists(files: Iterable[Dict]) -> bool:
    """Check whether replay.json is present (required for generation)."""
    return any(file.get("name") == "replay.json" for file in files)


def process_game(game_id: str, bucket: str, force: bool = False) -> str:
    """Generate and upload a video for a single game."""
    files = list_game_files(bucket, game_id)
    has_video = video_exists(files)
    has_replay = replay_exists(files)

    if has_video and not force:
        logger.info("%s: video already exists, skipping", game_id)
        return "skipped_existing"

    if not has_replay:
        logger.warning("%s: missing replay.json in storage, skipping", game_id)
        return "missing_replay"

    try:
        generator = SnakeVideoGenerator()
        result = generator.generate_and_upload(game_id)
        logger.info("%s: uploaded %s", game_id, result["public_url"])
        return "uploaded"
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("%s: failed to generate/upload (%s)", game_id, exc)
        return "failed"


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Backfill missing replay videos for all games")
    parser.add_argument(
        "--limit",
        type=int,
        help="Only process the first N games (default: all)",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Start processing from this offset in the games table",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=15,
        help="Number of parallel workers (default: 15)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even if replay.mp4 already exists in storage",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    bucket = os.getenv("SUPABASE_BUCKET", "matches")
    logger.info("Using bucket: %s", bucket)

    game_ids = fetch_game_ids(limit=args.limit, offset=args.offset)
    if not game_ids:
        logger.info("No games found to process")
        return

    logger.info("Processing %s games with %s workers...", len(game_ids), args.workers)

    results_counter: Dict[str, int] = {
        "uploaded": 0,
        "skipped_existing": 0,
        "missing_replay": 0,
        "failed": 0,
    }

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_game = {
            executor.submit(process_game, game_id, bucket, args.force): game_id
            for game_id in game_ids
        }

        for future in as_completed(future_to_game):
            status = future.result()
            if status in results_counter:
                results_counter[status] += 1

    logger.info(
        "Finished! Uploaded=%s, Skipped(existing)=%s, Missing replay=%s, Failed=%s",
        results_counter["uploaded"],
        results_counter["skipped_existing"],
        results_counter["missing_replay"],
        results_counter["failed"],
    )


if __name__ == "__main__":
    main()
