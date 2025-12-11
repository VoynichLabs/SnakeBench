#!/usr/bin/env python3
"""
Dry-run a placement sequence against the live leaderboard.

Loads DB credentials from .env, pulls ranked models, and replays a sequence
through placement_system to show which opponents would be scheduled and how
the skill estimate evolves.
"""

import sys
import argparse
from typing import List, Tuple

from dotenv import load_dotenv

load_dotenv()

try:
    from placement_system import (
        init_placement_state,
        select_next_opponent_with_reason,
        update_placement_state,
        ensure_interval_bounds,
    )
    from database_postgres import get_connection
except Exception as exc:
    print("Import/setup error. Ensure deps are installed (psycopg2, trueskill) and .env is present.")
    print(exc)
    sys.exit(1)


def fetch_ranked_models() -> List[Tuple[int, str, float, int]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id,
               name,
               trueskill_exposed,
               ROW_NUMBER() OVER (ORDER BY trueskill_exposed DESC NULLS LAST) - 1 AS rank_index
        FROM models
        WHERE is_active = TRUE
          AND test_status = 'ranked'
        ORDER BY trueskill_exposed DESC NULLS LAST
        """
    )
    rows = cur.fetchall()
    conn.close()
    return [
        (
            r["id"],
            r["name"],
            r.get("trueskill_exposed") or 0.0,
            r["rank_index"],
        )
        for r in rows
    ]


def build_sequence(name: str) -> List[Tuple[str, int, int, str, int]]:
    presets = {
        "default": [
            ("won", 5, 3, "body_collision", 40),
            ("won", 6, 4, "body_collision", 42),
            ("lost", 4, 6, "body_collision", 55),
            ("won", 7, 5, "body_collision", 50),
            ("won", 6, 4, "body_collision", 48),
            ("lost", 3, 7, "wall", 30),
        ],
        "zigzag": [  # W/L/L/W/W/L/W/L
            ("won", 6, 4, "body_collision", 42),
            ("lost", 4, 6, "body_collision", 45),
            ("lost", 3, 7, "body_collision", 50),
            ("won", 7, 5, "body_collision", 48),
            ("won", 6, 4, "body_collision", 52),
            ("lost", 2, 8, "wall", 30),
            ("won", 8, 6, "body_collision", 55),
            ("lost", 5, 7, "head_collision", 35),
        ],
        "win9": [("won", 7, 3, "body_collision", 45)] * 9,
    }
    seq = presets.get(name)
    if not seq:
        raise ValueError(f"Unknown sequence '{name}'. Options: {', '.join(presets.keys())}")
    return seq


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run placement sequence against live leaderboard.")
    parser.add_argument(
        "--sequence",
        default="default",
        choices=["default", "zigzag", "win9"],
        help="Which preset sequence to replay.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    ranked = fetch_ranked_models()
    if not ranked:
        print("No ranked models found.")
        return

    state = init_placement_state(model_id=9999, max_games=9)
    ensure_interval_bounds(state, ranked)

    sequence = build_sequence(args.sequence)

    for idx, (result, my_score, opp_score, death, rounds) in enumerate(sequence, 1):
        opponent, debug = select_next_opponent_with_reason(state, ranked_models=ranked)
        if not opponent:
            print(f"Game {idx}: no opponent available")
            break

        opp_id, opp_name, opp_rating, opp_rank = opponent
        game = {
            "opponent_id": opp_id,
            "result": result,
            "my_score": my_score,
            "opponent_score": opp_score,
            "my_death_reason": death,
            "total_rounds": rounds,
        }
        update_placement_state(state, game, opponent_rating=opp_rating)

        print(
            f"Game {idx}: vs {opp_name} (rank #{opp_rank}, rating {opp_rating:.2f}) -> {result} | "
            f"mu={state.skill.mu:.2f}, sigma={state.skill.sigma:.2f} | "
            f"interval=[{state.rating_low:.2f},{state.rating_high:.2f}] | probe={debug.get('probe')} "
            f"target={debug.get('target_rating'):.2f}"
        )


if __name__ == "__main__":
    main()
