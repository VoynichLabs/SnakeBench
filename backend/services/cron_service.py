"""
Lightweight cron-style service for scheduled maintenance tasks.

Currently includes:
 - Stale in-progress game cleanup every N minutes (default: 10)
 - OpenRouter catalog sync to insert new models as inactive/untested (default: daily)
"""

import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import schedule


# Ensure we can import database_postgres from the project root
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from database_postgres import get_connection  # noqa: E402
from cli.sync_openrouter_models import sync_models as sync_openrouter_models  # noqa: E402


LOG_LEVEL = os.getenv("CRON_LOG_LEVEL", "INFO").upper()
STALE_MINUTES = int(os.getenv("STALE_GAME_MAX_MINUTES", "30"))
CRON_INTERVAL_MINUTES = int(os.getenv("CRON_INTERVAL_MINUTES", "10"))
OPENROUTER_SYNC_ENABLED = os.getenv("OPENROUTER_SYNC_ENABLED", "true").lower() == "true"
OPENROUTER_SYNC_INTERVAL_MINUTES = int(
    os.getenv("OPENROUTER_SYNC_INTERVAL_MINUTES", "60")
)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SCHEDULER_LOOP_SLEEP_SECONDS = int(os.getenv("SCHEDULER_LOOP_SLEEP_SECONDS", "5"))

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _fetch_stale_game_ids(threshold: datetime) -> List[str]:
    """Return ids of in-progress games that have not updated since threshold."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id
            FROM games
            WHERE status = 'in_progress'
              AND updated_at < %s
            """,
            (threshold,),
        )
        rows = cursor.fetchall()
        return [row["id"] for row in rows]
    finally:
        conn.close()


def delete_stale_in_progress_games() -> None:
    """Delete in-progress games and participants that have been idle too long."""
    threshold = datetime.now(timezone.utc) - timedelta(minutes=STALE_MINUTES)
    stale_ids = _fetch_stale_game_ids(threshold)

    if not stale_ids:
        logger.info(
            "No stale in-progress games found (threshold: %s)", threshold.isoformat()
        )
        return

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Remove participants first to satisfy FK constraints
        cursor.execute(
            """
            DELETE FROM game_participants
            WHERE game_id = ANY(%s)
            """,
            (stale_ids,),
        )
        participants_deleted = cursor.rowcount or 0

        cursor.execute(
            """
            DELETE FROM games
            WHERE id = ANY(%s)
            """,
            (stale_ids,),
        )
        games_deleted = cursor.rowcount or 0

        conn.commit()
        logger.warning(
            "Deleted %s stale in-progress games (participants removed: %s). "
            "Threshold: %s",
            games_deleted,
            participants_deleted,
            threshold.isoformat(),
        )
    except Exception:
        conn.rollback()
        logger.exception("Failed to delete stale in-progress games")
        raise
    finally:
        conn.close()


def _validated_openrouter_interval() -> int:
    """Ensure we always use a positive interval for model sync."""
    if OPENROUTER_SYNC_INTERVAL_MINUTES <= 0:
        logger.warning(
            "OPENROUTER_SYNC_INTERVAL_MINUTES=%s is invalid; defaulting to 1440.",
            OPENROUTER_SYNC_INTERVAL_MINUTES,
        )
        return 1440
    return OPENROUTER_SYNC_INTERVAL_MINUTES


def sync_openrouter_catalog() -> None:
    """Pull OpenRouter catalog and upsert new models as inactive/untested."""
    if not OPENROUTER_SYNC_ENABLED:
        logger.info("OpenRouter sync disabled via OPENROUTER_SYNC_ENABLED=false.")
        return

    if not OPENROUTER_API_KEY:
        logger.warning(
            "Skipping OpenRouter model sync: OPENROUTER_API_KEY not set. "
            "Set it to enable catalog imports."
        )
        return

    try:
        logger.info("Starting OpenRouter model sync...")
        stats = sync_openrouter_models(api_key=OPENROUTER_API_KEY) or {}

        if stats.get("error"):
            logger.error("OpenRouter sync reported an error: %s", stats)
            return

        logger.info(
            "OpenRouter sync complete. total=%s added=%s updated=%s skipped=%s",
            stats.get("total", 0),
            stats.get("added", 0),
            stats.get("updated", 0),
            stats.get("skipped", 0),
        )
    except Exception:
        logger.exception("OpenRouter model sync failed")


def run_scheduler() -> None:
    """Start the scheduler loop."""
    logger.info(
        "Starting cron service. Cleanup every %s minutes; stale cutoff %s minutes.",
        CRON_INTERVAL_MINUTES,
        STALE_MINUTES,
    )

    schedule.every(CRON_INTERVAL_MINUTES).minutes.do(delete_stale_in_progress_games)

    # Run once on startup to catch existing stale records
    delete_stale_in_progress_games()

    if OPENROUTER_SYNC_ENABLED and OPENROUTER_API_KEY:
        sync_interval = _validated_openrouter_interval()
        schedule.every(sync_interval).minutes.do(sync_openrouter_catalog)
        logger.info(
            "Scheduled OpenRouter model sync every %s minutes.", sync_interval
        )
        # Initial run on startup to capture any missed models
        sync_openrouter_catalog()
    elif OPENROUTER_SYNC_ENABLED:
        logger.warning(
            "OpenRouter sync is enabled but OPENROUTER_API_KEY is missing; "
            "sync will not be scheduled."
        )
    else:
        logger.info("OpenRouter sync disabled; skipping schedule registration.")

    while True:
        schedule.run_pending()
        time.sleep(SCHEDULER_LOOP_SLEEP_SECONDS)


if __name__ == "__main__":
    run_scheduler()
