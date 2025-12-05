#!/usr/bin/env python3
"""
Undo a game by replaying all other games chronologically with TrueSkill and aggregates.

Steps:
- Reset all models to baseline TrueSkill and zeroed aggregates.
- Replay every game except the target in start_time order, updating aggregates + TrueSkill.
- Delete the target game's participants and the game row.

This keeps behavior deterministic and avoids maintaining separate rating logic.
"""

import argparse
import os
import sys
from typing import Iterable, List

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


def reset_models_and_stats() -> int:
    """
    Reset TrueSkill fields and aggregate stats to baseline.
    Returns number of rows updated.
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


def stream_game_ids(exclude_game_id: str) -> Iterable[str]:
    """
    Yield game ids in chronological order, excluding the target game.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id
            FROM games
            WHERE id <> %s
            ORDER BY start_time ASC NULLS FIRST, end_time ASC NULLS FIRST, id ASC
            """,
            (exclude_game_id,),
        )
        for row in cursor.fetchall():
            yield row["id"]
    finally:
        cursor.close()
        conn.close()


def game_exists(game_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM games WHERE id = %s", (game_id,))
        return cursor.fetchone() is not None
    finally:
        cursor.close()
        conn.close()


def delete_game_and_participants(game_id: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM game_participants WHERE game_id = %s", (game_id,))
        cursor.execute("DELETE FROM games WHERE id = %s", (game_id,))
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def replay_all_but_target(target_game_id: str) -> List[str]:
    """
    Reset state and replay all games except the target.
    Returns list of processed game ids.
    """
    updated_models = reset_models_and_stats()
    print(f"Reset {updated_models} models to baseline ratings and zeroed aggregates.")

    processed: List[str] = []
    for gid in stream_game_ids(target_game_id):
        update_model_aggregates(gid)
        update_trueskill_ratings(gid)
        processed.append(gid)
        if len(processed) % 100 == 0:
            print(f"Replayed {len(processed)} games...")
    return processed


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Undo a game by replaying all other games with TrueSkill.")
    parser.add_argument("game_id", help="The game id to undo (will be deleted)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform replay but do not delete the target game",
    )
    args = parser.parse_args()

    if not game_exists(args.game_id):
        print(f"Game {args.game_id} not found.")
        return

    processed = replay_all_but_target(args.game_id)
    print(f"Finished replaying {len(processed)} games (excluding {args.game_id}).")

    if args.dry_run:
        print("Dry run; target game not deleted.")
        return

    delete_game_and_participants(args.game_id)
    print(f"Deleted game {args.game_id} and its participants.")


if __name__ == "__main__":
    main()
