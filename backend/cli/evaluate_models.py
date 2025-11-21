#!/usr/bin/env python3
"""
Evaluate untested/testing models using binary-search placement in a fixed game budget.

This script:
  - Selects up to N models in states ('untested', 'testing') and is_active = TRUE.
  - Reconstructs placement state from completed evaluation games (game_type = 'evaluation').
  - Dispatches exactly one new evaluation game per model when needed (Celery task).
  - Finalizes models (test_status -> 'ranked') when their budget is exhausted or no opponents remain.

Idempotent: if interrupted, rerun and it will pick up from history.
"""

import argparse
import sys
import os
from typing import Dict, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_postgres import get_connection
from tasks import run_game_task
from placement_system import (
    init_placement_state,
    select_next_opponent,
    update_placement_interval,
    get_ranked_models_by_index,
)
from placement_system import get_opponent_rank_index
from data_access.api_queries import get_model_by_name


def fetch_candidates(conn, limit: int) -> List[Dict]:
    """
    Fetch up to `limit` models that need evaluation.
    Prioritize models already in testing, then pick fresh untested ones.
    """
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, name, test_status
        FROM models
        WHERE is_active = TRUE
          AND test_status IN ('untested', 'testing')
        ORDER BY
            CASE WHEN test_status = 'testing' THEN 0 ELSE 1 END,
            discovered_at ASC
        LIMIT %s
        """,
        (limit,),
    )
    return cursor.fetchall()


def has_pending_eval_game(conn, model_id: int) -> bool:
    """
    Check if the model already has a queued/in-progress evaluation game.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 1
        FROM games g
        JOIN game_participants gp ON gp.game_id = g.id
        WHERE gp.model_id = %s
          AND g.game_type = 'evaluation'
          AND g.status IN ('queued', 'in_progress')
        LIMIT 1
        """,
        (model_id,),
    )
    return cursor.fetchone() is not None


def fetch_eval_history(conn, model_id: int) -> List[Dict]:
    """
    Get completed evaluation games for the model with opponent + result.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            g.id AS game_id,
            g.start_time,
            gp.result AS model_result,
            (
                SELECT opp.model_id
                FROM game_participants opp
                WHERE opp.game_id = g.id
                  AND opp.model_id != gp.model_id
                LIMIT 1
            ) AS opponent_id
        FROM games g
        JOIN game_participants gp ON gp.game_id = g.id
        WHERE gp.model_id = %s
          AND g.game_type = 'evaluation'
          AND g.status = 'completed'
        ORDER BY g.start_time ASC
        """,
        (model_id,),
    )
    return cursor.fetchall()


def rebuild_state_from_history(
    model_id: int, max_games: int, history: List[Dict], ranked_models: List[Tuple[int, str, float, int]]
) -> Tuple[object, int]:
    """
    Recreate placement state based on completed evaluation games.
    """
    state = init_placement_state(model_id, max_games=max_games)

    for record in history:
        opponent_id = record.get("opponent_id")
        result = record.get("model_result")
        if not opponent_id or not result:
            continue

        opponent_rank_index = get_opponent_rank_index(opponent_id, ranked_models=ranked_models)
        if opponent_rank_index is None:
            continue

        update_placement_interval(state, opponent_rank_index, result)
        state.opponents_played.add(opponent_id)

    return state, len(history)


def mark_status(conn, model_id: int, status: str) -> None:
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE models SET test_status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (status, model_id),
    )
    conn.commit()


def finalize_model(conn, model_id: int, model_name: str) -> None:
    mark_status(conn, model_id, "ranked")
    print(f"✓ Finalized and ranked model: {model_name}")


def dispatch_eval_game(
    model_name: str,
    opponent_name: str,
    game_params: Dict[str, int],
) -> str:
    """
    Enqueue a single evaluation game between two named models.
    Returns Celery task ID.
    """
    config_a = get_model_by_name(model_name)
    config_b = get_model_by_name(opponent_name)

    if config_a is None or config_b is None:
        raise ValueError(f"Could not load configs for {model_name} vs {opponent_name}")

    result = run_game_task.apply_async(
        args=[config_a, config_b, {**game_params, "game_type": "evaluation"}],
    )
    return result.id


def count_ranked(conn) -> int:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) AS c FROM models WHERE test_status = 'ranked' AND is_active = TRUE"
    )
    row = cursor.fetchone()
    return row["c"] if row else 0


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate untested/testing models using binary-search placement."
    )
    parser.add_argument(
        "--max-models",
        type=int,
        default=5,
        help="Max models to evaluate in this run (default: 5).",
    )
    parser.add_argument(
        "--max-games",
        type=int,
        default=10,
        help="Max evaluation games per model (default: 10).",
    )
    parser.add_argument("--width", type=int, default=10, help="Board width.")
    parser.add_argument("--height", type=int, default=10, help="Board height.")
    parser.add_argument(
        "--max-rounds", type=int, default=100, help="Max rounds per game."
    )
    parser.add_argument(
        "--num-apples", type=int, default=5, help="Number of apples on the board."
    )

    args = parser.parse_args()

    conn = get_connection()

    ranked_models = get_ranked_models_by_index()
    ranked_count = len(ranked_models)
    if ranked_count == 0:
        print("✗ No ranked models available to compare against. Aborting.")
        return

    candidates = fetch_candidates(conn, args.max_models)
    if not candidates:
        print("No untested/testing models found.")
        return

    game_params = {
        "width": args.width,
        "height": args.height,
        "max_rounds": args.max_rounds,
        "num_apples": args.num_apples,
    }

    for candidate in candidates:
        model_id = candidate["id"]
        model_name = candidate["name"]
        status = candidate["test_status"]

        print(f"\n=== Evaluating {model_name} (status: {status}) ===")

        pending = has_pending_eval_game(conn, model_id)
        if pending:
            print("  • Pending evaluation game in progress; skipping enqueue.")
            continue

        history = fetch_eval_history(conn, model_id)
        state, completed = rebuild_state_from_history(
            model_id, max_games=args.max_games, history=history, ranked_models=ranked_models
        )

        print(
            f"  • Completed eval games: {completed}/{args.max_games} | interval=[{state.low},{state.high}]"
        )
        if completed >= args.max_games:
            finalize_model(conn, model_id, model_name)
            continue

        opponent = select_next_opponent(state, ranked_models=ranked_models)
        if not opponent:
            print("  • No suitable opponent found; finalizing.")
            finalize_model(conn, model_id, model_name)
            continue

        opponent_id, opponent_name, opponent_elo = opponent
        opponent_rank_index = get_opponent_rank_index(opponent_id, ranked_models=ranked_models)
        if opponent_rank_index is None:
            print("  • Opponent has no rank; skipping enqueue.")
            continue
        print(
            f"  • Next opponent: {opponent_name} (rank #{opponent_rank_index}, ELO {opponent_elo:.1f}) | task queued as evaluation"
        )

        try:
            task_id = dispatch_eval_game(model_name, opponent_name, game_params)
            print(f"  • Enqueued Celery task: {task_id}")
        except Exception as e:
            print(f"  ✗ Failed to enqueue game: {e}")
            continue

        if status == "untested":
            mark_status(conn, model_id, "testing")


if __name__ == "__main__":
    main()
