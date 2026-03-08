#!/usr/bin/env python3
"""
Dry-run a placement sequence against the live leaderboard.

Loads DB credentials from .env, pulls ranked models, and replays a sequence
through placement_system to show which opponents would be scheduled and how
the skill estimate evolves.
"""

import sys
import argparse
from typing import List, Tuple, Dict, Any

from dotenv import load_dotenv

load_dotenv()

try:
    from placement_system import (
        init_placement_state,
        select_next_opponent_with_reason,
        update_placement_state,
    )
    from database_postgres import get_connection
except Exception as exc:
    print("Import/setup error. Ensure deps are installed (psycopg2, trueskill) and .env is present.")
    print(exc)
    sys.exit(1)


def fetch_ranked_models() -> list:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id,
               name,
               trueskill_exposed,
               pricing_input,
               pricing_output,
               provider,
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
        {
            'id': r["id"],
            'name': r["name"],
            'rating': r.get("trueskill_exposed") or 0.0,
            'rank_index': r["rank_index"],
            'pricing_input': r.get("pricing_input"),
            'pricing_output': r.get("pricing_output"),
            'provider': r.get("provider"),
        }
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

    sequence = build_sequence(args.sequence)

    for idx, (result, my_score, opp_score, death, rounds) in enumerate(sequence, 1):
        opponent, debug = select_next_opponent_with_reason(state, ranked_models=ranked)
        if not opponent:
            print(f"Game {idx}: no opponent available")
            break

        opp_id = opponent['id']
        opp_name = opponent['name']
        opp_rating = opponent['rating']
        opp_rank = opponent['rank_index']
        game = {
            "opponent_id": opp_id,
            "result": result,
            "my_score": my_score,
            "opponent_score": opp_score,
            "my_death_reason": death,
            "total_rounds": rounds,
        }
        update_placement_state(state, game, opponent_rating=opp_rating)

        target = debug.get('target_rating')
        target_str = f"{target:.2f}" if target is not None else "N/A"
        pricing_target = debug.get('pricing_target')
        pricing_str = f"{pricing_target:.2f}" if pricing_target is not None else "N/A"
        alpha = debug.get('alpha')
        alpha_str = f"{alpha:.2f}" if alpha is not None else "N/A"
        print(
            f"Game {idx}: vs {opp_name} (rank #{opp_rank}, rating {opp_rating:.2f}) -> {result} | "
            f"mu={state.mu:.2f}, sigma={state.sigma:.2f}, exposed={state.exposed:.2f} | "
            f"target={target_str} pricing={pricing_str} alpha={alpha_str}"
        )


if __name__ == "__main__":
    main()
