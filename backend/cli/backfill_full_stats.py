#!/usr/bin/env python3
"""
Full leaderboard backfill:

- Optionally reset all models to baseline TrueSkill + zeroed aggregates.
- Replay games in chronological order to rebuild wins/losses/ties/apples/games_played.
- Recompute TrueSkill ratings game-by-game.

Use this after accidental resets or schema changes to restore a consistent leaderboard.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable, Iterator, List

from dotenv import load_dotenv

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database_postgres import get_connection  # noqa: E402
from data_access import (  # noqa: E402
    update_model_aggregates,
    update_trueskill_ratings,
)
from services.trueskill_engine import (  # noqa: E402
    DEFAULT_MU,
    DEFAULT_SIGMA,
    DISPLAY_MULTIPLIER,
)


def reset_models_to_baseline() -> int:
    """
    Reset TrueSkill and aggregate counters to baseline for all models.

    Returns:
        Number of rows updated.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        exposed = DEFAULT_MU - 3 * DEFAULT_SIGMA
        display = exposed * DISPLAY_MULTIPLIER
        cursor.execute(
            """
            UPDATE models
            SET trueskill_mu = %s,
                trueskill_sigma = %s,
                trueskill_updated_at = NOW(),
                elo_rating = %s,
                wins = 0,
                losses = 0,
                ties = 0,
                apples_eaten = 0,
                games_played = 0,
                last_played_at = NULL,
                updated_at = NOW()
            """,
            (DEFAULT_MU, DEFAULT_SIGMA, display),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        cursor.close()
        conn.close()


def stream_game_ids(
    limit: int | None = None,
    offset: int = 0,
    batch_size: int = 200,
    include_failed: bool = False,
) -> Iterator[str]:
    """
    Yield game ids in chronological order without loading the whole table.
    """
    where_clause = "" if include_failed else "WHERE status = 'completed'"
    query = f"""
        SELECT id
        FROM games
        {where_clause}
        ORDER BY start_time ASC NULLS FIRST, end_time ASC NULLS FIRST, id ASC
        LIMIT %s OFFSET %s
    """

    conn = get_connection()
    cursor = conn.cursor()
    fetched = 0
    current_offset = offset

    try:
        while True:
            take = batch_size
            if limit is not None:
                remaining = limit - fetched
                if remaining <= 0:
                    break
                take = min(take, remaining)

            cursor.execute(query, (take, current_offset))
            rows = cursor.fetchall()
            if not rows:
                break

            for row in rows:
                yield row["id"]

            fetched += len(rows)
            current_offset += len(rows)
    finally:
        cursor.close()
        conn.close()


def rebuild_from_history(
    limit: int | None = None,
    offset: int = 0,
    batch_size: int = 200,
    include_failed: bool = False,
    dry_run: bool = False,
) -> List[str]:
    """
    Replay games and update aggregates + TrueSkill in order.

    Returns:
        List of processed game ids (for logging/verification).
    """
    processed: List[str] = []
    for idx, game_id in enumerate(
        stream_game_ids(limit=limit, offset=offset, batch_size=batch_size, include_failed=include_failed),
        start=1,
    ):
        if dry_run:
            print(f"[dry-run] Would process game {game_id}")
        else:
            update_model_aggregates(game_id)
            update_trueskill_ratings(game_id)

        processed.append(game_id)
        if idx % 100 == 0:
            print(f"Processed {idx} games...")

    return processed


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Reset and backfill TrueSkill + aggregates from game history."
    )
    parser.add_argument("--limit", type=int, help="Number of games to process (default: all)")
    parser.add_argument("--offset", type=int, default=0, help="Offset into the games table")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="How many games to fetch per batch (default: 200)",
    )
    parser.add_argument(
        "--include-failed",
        action="store_true",
        help="Include non-completed games (default: completed only)",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Skip resetting models; continue from current ratings/aggregates",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without writing updates",
    )
    args = parser.parse_args()

    if not args.no_reset and not args.dry_run:
        count = reset_models_to_baseline()
        print(f"Reset {count} models to baseline ratings and zeroed aggregates.")
    elif args.no_reset:
        print("Skipping reset (continuing from current model ratings/aggregates).")
    else:
        print("[dry-run] Would reset all models to baseline.")

    processed = rebuild_from_history(
        limit=args.limit,
        offset=args.offset,
        batch_size=args.batch_size,
        include_failed=args.include_failed,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print(f"[dry-run] Would process {len(processed)} games.")
    else:
        print(f"Finished backfill for {len(processed)} games.")


if __name__ == "__main__":
    main()
