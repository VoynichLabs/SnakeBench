#!/usr/bin/env python3
"""
Utility: Delete all games involving a given model.

Deletes from game_participants (all participants in those games) and games.
Defaults to only evaluation games; use --all-types to include every game_type.

Example:
  python backend/cli/delete_model_games.py --model-id 123 --dry-run
  python backend/cli/delete_model_games.py --model-id 123 --all-types
"""

import argparse
import sys
import os
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database_postgres import get_connection  # noqa: E402


def fetch_games(conn, model_id: int, all_types: bool) -> List[Dict]:
    """Return games (ids and metadata) where the model participated."""
    cursor = conn.cursor()
    if all_types:
        cursor.execute(
            """
            SELECT g.id, g.game_type, g.status, g.start_time
            FROM games g
            JOIN game_participants gp ON gp.game_id = g.id
            WHERE gp.model_id = %s
            ORDER BY g.start_time ASC
            """,
            (model_id,),
        )
    else:
        cursor.execute(
            """
            SELECT g.id, g.game_type, g.status, g.start_time
            FROM games g
            JOIN game_participants gp ON gp.game_id = g.id
            WHERE gp.model_id = %s
              AND g.game_type = 'evaluation'
            ORDER BY g.start_time ASC
            """,
            (model_id,),
        )
    return cursor.fetchall()


def delete_games(conn, game_ids: List[str]) -> Dict[str, int]:
    """Delete participants and games for provided ids; returns counts."""
    cursor = conn.cursor()
    cursor.execute(
        """
        DELETE FROM game_participants
        WHERE game_id = ANY(%s)
        """,
        (game_ids,),
    )
    participants_deleted = cursor.rowcount or 0

    cursor.execute(
        """
        DELETE FROM games
        WHERE id = ANY(%s)
        """,
        (game_ids,),
    )
    games_deleted = cursor.rowcount or 0

    conn.commit()
    return {
        "participants_deleted": participants_deleted,
        "games_deleted": games_deleted,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Delete all games a model has played (games + participants)."
    )
    parser.add_argument(
        "--model-id",
        type=int,
        required=True,
        help="ID of the model to purge games for.",
    )
    parser.add_argument(
        "--all-types",
        action="store_true",
        help="Include all game types (default is evaluation only).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List games that would be deleted without modifying the DB.",
    )

    args = parser.parse_args()
    conn = get_connection()

    try:
        games = fetch_games(conn, args.model_id, all_types=args.all_types)
        if not games:
            print(f"No games found for model {args.model_id}.")
            return

        print(f"Found {len(games)} games for model {args.model_id}:")
        for g in games:
            print(
                f"  {g['id']} | type={g['game_type']} | status={g['status']} | start={g['start_time']}"
            )

        if args.dry_run:
            print("\nDry run only; no deletions performed.")
            return

        game_ids = [g["id"] for g in games]
        counts = delete_games(conn, game_ids)
        print(
            f"\nDeleted {counts['games_deleted']} games and "
            f"{counts['participants_deleted']} participants entries."
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
