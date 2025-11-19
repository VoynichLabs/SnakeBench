#!/usr/bin/env python3
"""
Cleanup stale in-progress games.

This script removes games that have status='in_progress' but haven't been
updated in the last 30 minutes. These are considered abandoned/stale games.
"""

import sys
import os
from datetime import datetime, timedelta, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_postgres import get_connection


def cleanup_stale_games(minutes_threshold: int = 30, dry_run: bool = False):
    """
    Delete games with status='in_progress' that haven't been updated recently.

    Args:
        minutes_threshold: Number of minutes of inactivity to consider a game stale
        dry_run: If True, only show what would be deleted without actually deleting
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Calculate the cutoff time (UTC)
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes_threshold)

        # First, find stale games
        cursor.execute("""
            SELECT id, start_time, rounds
            FROM games
            WHERE status = 'in_progress'
            AND start_time < %s
            ORDER BY start_time
        """, (cutoff_time,))

        stale_games = cursor.fetchall()

        if not stale_games:
            print(f"No stale games found (no in_progress games older than {minutes_threshold} minutes)")
            return

        print(f"\nFound {len(stale_games)} stale in_progress game(s):")
        print("-" * 80)
        for game in stale_games:
            age_minutes = (datetime.now(timezone.utc) - game['start_time']).total_seconds() / 60
            print(f"  Game ID: {game['id']}")
            print(f"  Started: {game['start_time']}")
            print(f"  Age: {age_minutes:.1f} minutes")
            print(f"  Rounds: {game['rounds'] or 0}")
            print()

        if dry_run:
            print("DRY RUN - No games were deleted. Run without --dry-run to actually delete.")
            return

        # Delete the stale games and their participants
        game_ids = [game['id'] for game in stale_games]

        # Delete participants first (foreign key constraint)
        cursor.execute("""
            DELETE FROM game_participants
            WHERE game_id = ANY(%s)
        """, (game_ids,))
        participants_deleted = cursor.rowcount

        # Delete the games
        cursor.execute("""
            DELETE FROM games
            WHERE id = ANY(%s)
        """, (game_ids,))
        games_deleted = cursor.rowcount

        conn.commit()

        print("-" * 80)
        print(f"✓ Deleted {games_deleted} stale game(s)")
        print(f"✓ Deleted {participants_deleted} associated participant record(s)")

    except Exception as e:
        print(f"✗ Error cleaning up stale games: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clean up stale in-progress games")
    parser.add_argument(
        "--minutes",
        type=int,
        default=30,
        help="Consider games stale after this many minutes of inactivity (default: 30)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )

    args = parser.parse_args()

    print(f"Cleaning up in_progress games older than {args.minutes} minutes...")
    cleanup_stale_games(minutes_threshold=args.minutes, dry_run=args.dry_run)
