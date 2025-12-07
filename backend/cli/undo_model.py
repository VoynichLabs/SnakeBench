#!/usr/bin/env python3
"""
Undo all games for a single model without resetting everyone else.

Steps:
- Set the model's test_status back to testing (configurable).
- Delete games the model participated in (evaluation only by default).
- Reset TrueSkill/aggregate stats for the model (and, optionally, directly impacted
  opponents) to the baseline, then replay only those models' remaining games to
  approximate fresh ratings.

This is intentionally approximate; it avoids a full global replay.
"""

import argparse
import os
import sys
from typing import Dict, Iterable, List, Set

from dotenv import load_dotenv

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database_postgres import get_connection  # noqa: E402
from services.trueskill_engine import (  # noqa: E402
    DEFAULT_MU,
    DEFAULT_SIGMA,
    DISPLAY_MULTIPLIER,
    trueskill_engine,
)
from data_access.repositories.model_repository import ModelRepository  # noqa: E402


def fetch_model(conn, model_id: int) -> Dict:
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, name, test_status
            FROM models
            WHERE id = %s
            """,
            (model_id,),
        )
        return cursor.fetchone()
    finally:
        cursor.close()


def fetch_games(conn, model_id: int, all_types: bool) -> List[Dict]:
    cursor = conn.cursor()
    try:
        if all_types:
            cursor.execute(
                """
                SELECT g.id, g.game_type, g.status, g.start_time
                FROM games g
                JOIN game_participants gp ON gp.game_id = g.id
                WHERE gp.model_id = %s
                ORDER BY g.start_time ASC NULLS FIRST, g.id ASC
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
                ORDER BY g.start_time ASC NULLS FIRST, g.id ASC
                """,
                (model_id,),
            )
        return cursor.fetchall()
    finally:
        cursor.close()


def collect_impacted_models(conn, game_ids: List[str]) -> Set[int]:
    if not game_ids:
        return set()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT DISTINCT model_id
            FROM game_participants
            WHERE game_id = ANY(%s)
            """,
            (game_ids,),
        )
        return {row["model_id"] for row in cursor.fetchall()}
    finally:
        cursor.close()


def delete_games(conn, game_ids: List[str]) -> Dict[str, int]:
    if not game_ids:
        return {"games_deleted": 0, "participants_deleted": 0}

    cursor = conn.cursor()
    try:
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
            "games_deleted": games_deleted,
            "participants_deleted": participants_deleted,
        }
    finally:
        cursor.close()


def reset_models_to_baseline(
    conn, model_ids: Iterable[int], status_override: Dict[int, str] | None = None
) -> None:
    """
    Reset TrueSkill and aggregates for provided models to the baseline.
    Optionally override test_status per model (used for the target model).
    """
    model_ids = list(model_ids)
    if not model_ids:
        return

    cursor = conn.cursor()
    try:
        exposed = DEFAULT_MU - 3 * DEFAULT_SIGMA
        display = exposed * DISPLAY_MULTIPLIER

        for mid in model_ids:
            status = (status_override or {}).get(mid)
            if status:
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
                        test_status = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (DEFAULT_MU, DEFAULT_SIGMA, display, status, mid),
                )
            else:
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
                    WHERE id = %s
                    """,
                    (DEFAULT_MU, DEFAULT_SIGMA, display, mid),
                )
        conn.commit()
    finally:
        cursor.close()


def recompute_aggregates_for_models(conn, model_ids: Iterable[int]) -> None:
    """
    Recompute aggregates for a subset of models from remaining games.
    """
    model_ids = list(model_ids)
    if not model_ids:
        return

    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            WITH agg AS (
                SELECT
                    gp.model_id,
                    SUM(CASE WHEN gp.result = 'won' THEN 1 ELSE 0 END) AS wins,
                    SUM(CASE WHEN gp.result = 'lost' THEN 1 ELSE 0 END) AS losses,
                    SUM(CASE WHEN gp.result = 'tied' THEN 1 ELSE 0 END) AS ties,
                    SUM(gp.score) AS apples_eaten,
                    COUNT(*) AS games_played,
                    MAX(g.start_time) AS last_played_at
                FROM game_participants gp
                JOIN games g ON g.id = gp.game_id
                WHERE gp.model_id = ANY(%s)
                GROUP BY gp.model_id
            )
            UPDATE models m
            SET wins = COALESCE(a.wins, 0),
                losses = COALESCE(a.losses, 0),
                ties = COALESCE(a.ties, 0),
                apples_eaten = COALESCE(a.apples_eaten, 0),
                games_played = COALESCE(a.games_played, 0),
                last_played_at = a.last_played_at,
                updated_at = NOW()
            FROM agg a
            WHERE m.id = a.model_id
            """,
            (model_ids,),
        )

        cursor.execute(
            """
            UPDATE models m
            SET wins = 0,
                losses = 0,
                ties = 0,
                apples_eaten = 0,
                games_played = 0,
                last_played_at = NULL,
                updated_at = NOW()
            WHERE m.id = ANY(%s)
              AND NOT EXISTS (
                  SELECT 1 FROM game_participants gp WHERE gp.model_id = m.id
              )
            """,
            (model_ids,),
        )
        conn.commit()
    finally:
        cursor.close()


def stream_games_for_models(conn, model_ids: Iterable[int]) -> Iterable[str]:
    """
    Yield game ids (chronological) that include any of the provided models.
    """
    model_ids = list(model_ids)
    if not model_ids:
        return []

    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT g.id, g.start_time
            FROM games g
            JOIN game_participants gp ON gp.game_id = g.id
            WHERE gp.model_id = ANY(%s)
            GROUP BY g.id, g.start_time
            ORDER BY g.start_time ASC NULLS FIRST, g.id ASC
            """,
            (model_ids,),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
    for row in rows:
        yield row["id"]


def replay_trueskill_for_models(model_ids: Set[int]) -> int:
    """
    Approximate TrueSkill rebuild: for games involving the impacted models,
    recompute updates but only persist the impacted models' rows.
    """
    if not model_ids:
        return 0

    processed = 0
    repo = ModelRepository()
    conn = get_connection()
    try:
        for gid in stream_games_for_models(conn, model_ids):
            updates = trueskill_engine.rate_game(gid, persist=False, log=False)
            scoped = [u for u in updates if u["model_id"] in model_ids]
            if scoped:
                repo.update_trueskill_batch(scoped)
            processed += 1
            if processed % 100 == 0:
                print(f"Replayed {processed} games for impacted cohort...")
        return processed
    finally:
        conn.close()


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Undo all games for a model and reset its ratings without a global rebuild."
    )
    parser.add_argument(
        "--model-id",
        type=int,
        required=True,
        help="ID of the model to reset.",
    )
    parser.add_argument(
        "--status",
        default="testing",
        help="Test status to set for the target model (default: testing).",
    )
    parser.add_argument(
        "--all-types",
        action="store_true",
        help="Include all game types (default: evaluation only).",
    )
    parser.add_argument(
        "--model-only",
        action="store_true",
        help="Only reset/replay the target model (ignore opponents).",
    )
    parser.add_argument(
        "--skip-replay",
        action="store_true",
        help="Skip TrueSkill replay for the impacted cohort (baseline reset only).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed/reset without writing to the DB.",
    )

    args = parser.parse_args()
    conn = get_connection()

    try:
        model = fetch_model(conn, args.model_id)
        if not model:
            print(f"Model {args.model_id} not found.")
            return

        games = fetch_games(conn, args.model_id, all_types=args.all_types)
        game_ids = [g["id"] for g in games]

        impacted_models = collect_impacted_models(conn, game_ids)
        impacted_models.add(args.model_id)
        if args.model_only:
            impacted_models = {args.model_id}

        print(f"Target model: {model['name']} (id={model['id']}, status={model['test_status']})")
        print(f"Games to delete: {len(game_ids)}")
        if games:
            preview = games[:5]
            for g in preview:
                print(
                    f"  {g['id']} | type={g['game_type']} | status={g['status']} | start={g['start_time']}"
                )
            if len(games) > len(preview):
                print(f"  ... (+{len(games) - len(preview)} more)")

        print(f"Impacted models to reset/replay: {sorted(impacted_models)}")

        if args.dry_run:
            print("\nDry run only; no changes applied.")
            return

        counts = delete_games(conn, game_ids)
        print(
            f"Deleted {counts['games_deleted']} games and "
            f"{counts['participants_deleted']} participant rows."
        )

        reset_models_to_baseline(conn, impacted_models, status_override={args.model_id: args.status})
        print(f"Reset {len(impacted_models)} models to baseline rating/aggregates.")

        recompute_aggregates_for_models(conn, impacted_models)
        print("Recomputed aggregates for impacted models.")

        if not args.skip_replay:
            processed = replay_trueskill_for_models(impacted_models)
            print(f"Replayed TrueSkill for {processed} games touching impacted models.")
        else:
            print("Skipped TrueSkill replay per --skip-replay.")

        print("Done.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
