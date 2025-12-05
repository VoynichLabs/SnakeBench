#!/usr/bin/env python3
"""
Backfill TrueSkill ratings game-by-game with optional interactive stepping.

- Resets all models to the baseline TrueSkill values when --reset is provided
- Streams games chronologically (start_time ASC NULLS FIRST, then end_time)
- Persists mu/sigma/exposed (and the ELO-compatible display alias) for each game
- Shows per-game deltas so you can sanity-check the migration one game at a time
"""

import argparse
import os
import sys
from typing import Dict, Iterable, Iterator, List

from dotenv import load_dotenv

# Add backend directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database_postgres import get_connection  # noqa: E402
from services.trueskill_engine import (  # noqa: E402
    TrueSkillEngine,
    DEFAULT_MU,
    DEFAULT_SIGMA,
    DISPLAY_MULTIPLIER,
)


GameRow = Dict[str, object]
UpdateRow = Dict[str, object]


def reset_all_models() -> None:
    """Set every model's TrueSkill fields back to the defaults."""
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
                updated_at = NOW()
            """,
            (DEFAULT_MU, DEFAULT_SIGMA, display),
        )
        conn.commit()
        print(
            f"Reset {cursor.rowcount} models to mu={DEFAULT_MU}, sigma={DEFAULT_SIGMA}, "
            f"exposed~{exposed:.3f} (elo/display alias {display:.1f})"
        )
    finally:
        cursor.close()
        conn.close()


def count_games(conn, include_failed: bool) -> int:
    where_clause = "" if include_failed else "WHERE status = 'completed'"
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT COUNT(*) AS count FROM games {where_clause}")
        row = cursor.fetchone()
        return int(row["count"]) if row else 0
    finally:
        cursor.close()


def stream_games(
    conn,
    limit: int | None = None,
    offset: int = 0,
    batch_size: int = 200,
    include_failed: bool = False,
) -> Iterator[GameRow]:
    """
    Yield games in chronological order without loading the whole table at once.
    """
    where_clause = "" if include_failed else "WHERE status = 'completed'"
    query = f"""
        SELECT id, start_time, end_time, total_score, rounds, status
        FROM games
        {where_clause}
        ORDER BY start_time ASC NULLS FIRST, end_time ASC NULLS FIRST, id ASC
        LIMIT %s OFFSET %s
    """

    cursor = conn.cursor()
    fetched = 0
    current_offset = offset

    try:
        while True:
            if limit is not None:
                remaining = limit - fetched
                if remaining <= 0:
                    break
                take = min(batch_size, remaining)
            else:
                take = batch_size

            cursor.execute(query, (take, current_offset))
            rows = cursor.fetchall()
            if not rows:
                break

            for row in rows:
                yield row

            fetched += len(rows)
            current_offset += len(rows)
    finally:
        cursor.close()


def history_table_exists(conn) -> bool:
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT to_regclass('public.model_rating_history') AS reg")
        row = cursor.fetchone()
        return bool(row and row.get("reg"))
    finally:
        cursor.close()


def insert_history_rows(conn, game_id: str, updates: Iterable[UpdateRow]) -> None:
    """
    Persist per-game rating snapshots if model_rating_history exists.
    """
    rows = [
        (
            game_id,
            u["model_id"],
            u["pre_mu"],
            u["pre_sigma"],
            u["mu"],
            u["sigma"],
            u["exposed"],
        )
        for u in updates
    ]
    if not rows:
        return

    cursor = conn.cursor()
    try:
        cursor.executemany(
            """
            INSERT INTO model_rating_history (
                game_id, model_id, pre_mu, pre_sigma, post_mu, post_sigma, exposed
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (game_id, model_id) DO UPDATE
            SET pre_mu = EXCLUDED.pre_mu,
                pre_sigma = EXCLUDED.pre_sigma,
                post_mu = EXCLUDED.post_mu,
                post_sigma = EXCLUDED.post_sigma,
                exposed = EXCLUDED.exposed
            """,
            rows,
        )
        conn.commit()
    finally:
        cursor.close()


def describe_update(u: UpdateRow) -> str:
    pre = f"mu={u['pre_mu']:.3f}, σ={u['pre_sigma']:.3f}, exp={u['pre_exposed']:.3f}, disp={u['pre_display_rating']:.1f}"
    post = f"mu={u['mu']:.3f}, σ={u['sigma']:.3f}, exp={u['exposed']:.3f}, disp={u['display_rating']:.1f}"
    delta = (
        f"Δmu={u['delta_mu']:+.3f}, Δσ={u['delta_sigma']:+.3f}, "
        f"Δexp={u['delta_exposed']:+.3f}, Δdisp={u['delta_display_rating']:+.1f}"
    )
    return (
        f"slot {u['player_slot']}: {u['model_name']} "
        f"[{u['result']}, score={u['score']}] {pre} -> {post} ({delta})"
    )


def print_game_summary(game: GameRow, updates: List[UpdateRow], index: int, total: int | None, dry_run: bool) -> None:
    prefix = f"[{index}"
    if total is not None:
        prefix += f"/{total}"
    prefix += "]"

    header = (
        f"{prefix} Game {game['id']} "
        f"start={game.get('start_time')} end={game.get('end_time')} "
        f"status={game.get('status')} rounds={game.get('rounds')}"
    )
    if dry_run:
        header += " (dry-run; not persisted)"

    print(header)
    for u in sorted(updates, key=lambda r: r["player_slot"]):
        print("  " + describe_update(u))
    print("")


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Replay games chronologically to backfill TrueSkill ratings."
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
        "--reset",
        action="store_true",
        help="Reset all models to the baseline TrueSkill values before replaying",
    )
    parser.add_argument(
        "--step",
        dest="step",
        action="store_true",
        help="Pause after each game to inspect updates",
    )
    parser.add_argument(
        "--no-step",
        dest="step",
        action="store_false",
        help="Process without waiting between games",
    )
    parser.set_defaults(step=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute updates without persisting them to the database",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Write model_rating_history rows when the table exists",
    )
    args = parser.parse_args()

    if args.reset:
        reset_all_models()

    conn = get_connection()
    try:
        total_games = count_games(conn, args.include_failed)
        to_process = total_games - args.offset
        if args.limit is not None:
            to_process = min(to_process, args.limit)
        print(
            f"Starting TrueSkill backfill from offset {args.offset} "
            f"({to_process if to_process >= 0 else 0} games to process)..."
        )

        engine = TrueSkillEngine()
        history_enabled = args.history and history_table_exists(conn)
        if args.history and not history_enabled:
            print("model_rating_history not found; history writes will be skipped.")

        for idx, game in enumerate(
            stream_games(
                conn,
                limit=args.limit,
                offset=args.offset,
                batch_size=args.batch_size,
                include_failed=args.include_failed,
            ),
            start=1,
        ):
            updates = engine.rate_game(
                game_id=game["id"],
                persist=not args.dry_run,
                log=False,
            )
            if not updates:
                print(f"Skipped game {game['id']} (not enough participants)")
                continue

            print_game_summary(game, updates, idx, to_process if to_process >= 0 else None, args.dry_run)

            if history_enabled and not args.dry_run:
                insert_history_rows(conn, game["id"], updates)

            if args.step:
                user_input = input("Press Enter for next game, or 'q' to quit: ").strip().lower()
                if user_input.startswith("q"):
                    print("Stopping at user request.")
                    break
    finally:
        conn.close()


if __name__ == "__main__":
    main()
