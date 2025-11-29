#!/usr/bin/env python3
"""
Bulk-migrate Supabase Storage replays to the new frames-based schema.

Assumptions:
  - Replays are stored at <bucket>/<game_id>/replay.json
  - You have SUPABASE_URL, SUPABASE_SERVICE_ROLE, and SUPABASE_BUCKET (default: matches) set

Usage examples:
  # Dry run: list and attempt conversion without uploading
  python migrate_replays_supabase.py --dry-run

  # Migrate all replays with up to 5 concurrent workers
  python migrate_replays_supabase.py --workers 5

  # Restrict to specific game IDs (comma-separated)
  python migrate_replays_supabase.py --game-ids 123,456
"""

import argparse
import concurrent.futures
import json
import logging
import sys
import os
from typing import Dict, Any, List, Tuple, Optional
from dotenv import load_dotenv

load_dotenv()

# Ensure the backend root is on the path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.supabase_client import get_supabase_client
from cli.migrate_replays import migrate_replay


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


def list_game_folders(storage, bucket: str) -> List[str]:
    """List top-level entries (game folders) in the bucket."""
    games: List[str] = []
    offset = 0
    page_size = 100

    while True:
        items = storage.from_(bucket).list(path="", options={"limit": page_size, "offset": offset})
        if not items:
            break
        for item in items:
            name = item.get("name")
            if name:
                games.append(name)
        offset += page_size

    return games


def download_replay(storage, bucket: str, game_id: str) -> Optional[Dict[str, Any]]:
    """Download replay.json for a given game_id."""
    path = f"{game_id}/replay.json"
    try:
        data = storage.from_(bucket).download(path)
        return json.loads(data)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to download %s: %s", path, exc)
        return None


def upload_replay(storage, bucket: str, game_id: str, replay: Dict[str, Any]) -> bool:
    """Upload migrated replay back to the same path with upsert."""
    path = f"{game_id}/replay.json"
    try:
        payload = json.dumps(replay, indent=2).encode("utf-8")
        storage.from_(bucket).upload(
            path=path,
            file=payload,
            file_options={"content-type": "application/json", "upsert": "true"}
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to upload %s: %s", path, exc)
        return False


def migrate_one(storage, bucket: str, game_id: str, dry_run: bool = False) -> Tuple[str, bool, str]:
    """Download, migrate, and upload one replay."""
    raw = download_replay(storage, bucket, game_id)
    if raw is None:
        return game_id, False, "download_failed"

    try:
        migrated = migrate_replay(raw)
    except Exception as exc:  # noqa: BLE001
        return game_id, False, f"migrate_failed: {exc}"

    if dry_run:
        return game_id, True, "dry_run"

    ok = upload_replay(storage, bucket, game_id, migrated)
    return game_id, ok, "uploaded" if ok else "upload_failed"


def main():
    parser = argparse.ArgumentParser(description="Migrate all Supabase replays to frames-based schema.")
    parser.add_argument("--bucket", default=None, help="Supabase bucket name (default: SUPABASE_BUCKET or 'matches').")
    parser.add_argument("--workers", type=int, default=5, help="Max concurrent workers (default: 5).")
    parser.add_argument("--game-ids", type=str, help="Comma-separated game IDs to migrate (default: all).")
    parser.add_argument("--dry-run", action="store_true", help="Do not upload, just attempt conversion.")
    args = parser.parse_args()

    storage = get_supabase_client().storage
    bucket = args.bucket or "matches"

    if args.game_ids:
        game_ids = [gid.strip() for gid in args.game_ids.split(",") if gid.strip()]
    else:
        logger.info("Listing game folders in bucket '%s'...", bucket)
        game_ids = list_game_folders(storage, bucket)
        logger.info("Found %s game folders", len(game_ids))

    if not game_ids:
        logger.info("No game IDs to process. Exiting.")
        return

    total = len(game_ids)
    logger.info("Starting migration with %s worker(s). Dry-run=%s. Total=%s", args.workers, args.dry_run, total)

    successes = 0
    failures = 0
    processed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_game = {
            executor.submit(migrate_one, storage, bucket, gid, args.dry_run): gid
            for gid in game_ids
        }

        for future in concurrent.futures.as_completed(future_to_game):
            gid = future_to_game[future]
            try:
                game_id, ok, status = future.result()
                processed += 1
                if ok:
                    successes += 1
                else:
                    failures += 1
                logger.info("[%s/%s] %s (%s)", processed, total, game_id, status)
            except Exception as exc:  # noqa: BLE001
                processed += 1
                failures += 1
                logger.error("[%s/%s] %s (exception: %s)", processed, total, gid, exc)

    logger.info("Done. Successes: %s | Failures: %s | Total: %s", successes, failures, total)


if __name__ == "__main__":
    main()
