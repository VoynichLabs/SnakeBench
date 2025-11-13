#!/usr/bin/env python3
"""
Validate that incremental ELO updates match elo_tracker.py recompute logic.

This script:
1. Captures current ELO ratings from the database
2. Simulates a fresh recompute using elo_tracker.py logic on all games
3. Compares the results to verify consistency
"""

from database import get_connection
import json
from datetime import datetime

# Import ELO logic from elo_tracker.py
K = 32
INITIAL_RATING = 1500
RESULT_RANK = {"won": 2, "tied": 1, "lost": 0}


def get_pair_result(result_i, result_j):
    """Match elo_tracker.py logic."""
    rank_i = RESULT_RANK.get(result_i, 1)
    rank_j = RESULT_RANK.get(result_j, 1)
    if rank_i > rank_j:
        return 1, 0
    elif rank_i < rank_j:
        return 0, 1
    else:
        return 0.5, 0.5


def expected_score(rating_i, rating_j):
    """Match elo_tracker.py logic."""
    return 1 / (1 + 10 ** ((rating_j - rating_i) / 400))


def recompute_elo_from_scratch():
    """
    Recompute ELO ratings from all games in the database using the same
    algorithm as elo_tracker.py.

    Returns:
        dict: model_name -> recomputed_elo_rating
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Get all games ordered by start_time (chronological)
    cursor.execute("""
        SELECT id, start_time
        FROM games
        ORDER BY start_time ASC
    """)
    games = cursor.fetchall()

    # Initialize ratings dict
    ratings = {}

    # Process each game
    for game_id, start_time in games:
        # Get participants for this game
        cursor.execute("""
            SELECT m.name, gp.result
            FROM game_participants gp
            JOIN models m ON gp.model_id = m.id
            WHERE gp.game_id = ?
            ORDER BY gp.player_slot
        """, (game_id,))

        participants = cursor.fetchall()
        if len(participants) < 2:
            continue

        # Initialize any new models
        for model_name, _ in participants:
            if model_name not in ratings:
                ratings[model_name] = INITIAL_RATING

        # Build lists for pairwise comparison
        n = len(participants)
        models = [p[0] for p in participants]
        results = [p[1] for p in participants]

        # Accumulate scores
        score_sum = {model: 0 for model in models}
        expected_sum = {model: 0 for model in models}

        # Loop over all unordered pairs
        for i in range(n):
            for j in range(i + 1, n):
                model_i = models[i]
                model_j = models[j]
                res_i = results[i]
                res_j = results[j]

                # Head-to-head result
                S_i, S_j = get_pair_result(res_i, res_j)

                # Expected scores
                R_i = ratings[model_i]
                R_j = ratings[model_j]
                E_i = expected_score(R_i, R_j)
                E_j = expected_score(R_j, R_i)

                # Accumulate
                score_sum[model_i] += S_i
                score_sum[model_j] += S_j
                expected_sum[model_i] += E_i
                expected_sum[model_j] += E_j

        # Update ratings
        for model in models:
            delta = (K / (n - 1)) * (score_sum[model] - expected_sum[model]) if (n > 1) else 0
            ratings[model] += delta

    conn.close()
    return ratings


def main():
    print("=" * 70)
    print("ELO Consistency Validation")
    print("=" * 70)
    print("\nComparing incremental DB updates vs. full recompute...")

    # 1. Get current ELO ratings from database
    print("\n1. Reading current ELO ratings from database...")
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name, elo_rating, games_played
        FROM models
        WHERE games_played > 0
        ORDER BY name
    """)

    db_ratings = {row[0]: {'elo': row[1], 'games': row[2]} for row in cursor.fetchall()}
    print(f"   Found {len(db_ratings)} models with games played")

    # 2. Recompute ELO from scratch
    print("\n2. Recomputing ELO ratings from all games...")
    recomputed = recompute_elo_from_scratch()
    print(f"   Recomputed ratings for {len(recomputed)} models")

    # 3. Compare the results
    print("\n3. Comparing results...")
    print(f"\n   {'Model':<40} {'DB ELO':>12} {'Recomputed':>12} {'Delta':>12}")
    print("   " + "-" * 78)

    max_delta = 0
    total_delta = 0
    count = 0

    for model_name in sorted(db_ratings.keys()):
        db_elo = db_ratings[model_name]['elo']
        recomp_elo = recomputed.get(model_name, INITIAL_RATING)
        delta = abs(db_elo - recomp_elo)

        max_delta = max(max_delta, delta)
        total_delta += delta
        count += 1

        # Only show models with significant differences
        if delta > 0.01:
            print(f"   {model_name:<40} {db_elo:>12.2f} {recomp_elo:>12.2f} {delta:>12.2f}")

    avg_delta = total_delta / count if count > 0 else 0

    print("   " + "-" * 78)
    print(f"\n   Statistics:")
    print(f"   - Models compared: {count}")
    print(f"   - Maximum delta: {max_delta:.4f}")
    print(f"   - Average delta: {avg_delta:.4f}")

    # 4. Verdict
    print("\n" + "=" * 70)
    if max_delta < 0.01:
        print("✓ VALIDATION PASSED")
        print("=" * 70)
        print("\nIncremental ELO updates match elo_tracker.py recompute logic.")
        print("Phase 2 implementation is consistent with the batch processing approach.")
    elif max_delta < 1.0:
        print("⚠ VALIDATION WARNING")
        print("=" * 70)
        print(f"\nSmall differences detected (max delta: {max_delta:.4f})")
        print("This may be due to floating-point precision or rounding.")
        print("Review the differences above to determine if they are acceptable.")
    else:
        print("✗ VALIDATION FAILED")
        print("=" * 70)
        print(f"\nSignificant differences detected (max delta: {max_delta:.4f})")
        print("The incremental ELO updates do not match the recompute logic.")
        print("Review the model_updates.py implementation.")

    conn.close()


if __name__ == "__main__":
    main()
