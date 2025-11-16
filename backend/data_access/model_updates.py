"""
Model statistics update functions including ELO ratings and aggregates.

Uses the same ELO calculation logic as elo_tracker.py to ensure consistency.
"""

import sqlite3
from typing import Dict, List, Any
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_postgres import get_connection

# ELO parameters (matching elo_tracker.py)
K = 32
INITIAL_RATING = 1500

# Result ranking (matching elo_tracker.py)
RESULT_RANK = {"won": 2, "tied": 1, "lost": 0}


def get_pair_result(result_i: str, result_j: str) -> tuple:
    """
    Given the result strings for two players, return head-to-head scores.

    Returns:
        Tuple (S_i, S_j) where S = 1 means win, 0 means loss, 0.5 means tie.

    This matches the logic in elo_tracker.py.
    """
    rank_i = RESULT_RANK.get(result_i, 1)
    rank_j = RESULT_RANK.get(result_j, 1)
    if rank_i > rank_j:
        return 1, 0
    elif rank_i < rank_j:
        return 0, 1
    else:
        return 0.5, 0.5


def expected_score(rating_i: float, rating_j: float) -> float:
    """
    Compute the expected score for player i vs. player j.

    This matches the logic in elo_tracker.py.
    """
    return 1 / (1 + 10 ** ((rating_j - rating_i) / 400))


def update_elo_ratings(game_id: str) -> None:
    """
    Update ELO ratings for all participants in a game using pairwise comparisons.

    This implements the same algorithm as elo_tracker.py process_game() function,
    computing pairwise expected/actual scores and updating ratings incrementally.

    Args:
        game_id: The game identifier to process
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Get all participants for this game with their current ELO ratings
        cursor.execute("""
            SELECT
                gp.model_id,
                gp.result,
                m.elo_rating,
                m.name
            FROM game_participants gp
            JOIN models m ON gp.model_id = m.id
            WHERE gp.game_id = %s
            ORDER BY gp.player_slot
        """, (game_id,))

        participants = cursor.fetchall()

        if len(participants) < 2:
            print(f"Game {game_id} has fewer than 2 participants, skipping ELO update")
            return

        # Build lists for easier iteration
        n = len(participants)
        model_ids = [p['model_id'] for p in participants]
        results = [p['result'] for p in participants]
        ratings = {p['model_id']: p['elo_rating'] for p in participants}
        names = {p['model_id']: p['name'] for p in participants}

        # Accumulate actual and expected scores for each model (pairwise)
        score_sum = {mid: 0 for mid in model_ids}
        expected_sum = {mid: 0 for mid in model_ids}

        # Loop over all unordered pairs of players
        for i in range(n):
            for j in range(i + 1, n):
                mid_i = model_ids[i]
                mid_j = model_ids[j]
                res_i = results[i]
                res_j = results[j]

                # Determine the head-to-head result
                S_i, S_j = get_pair_result(res_i, res_j)

                # Compute expected scores from current ratings
                R_i = ratings[mid_i]
                R_j = ratings[mid_j]
                E_i = expected_score(R_i, R_j)
                E_j = expected_score(R_j, R_i)

                # Accumulate results
                score_sum[mid_i] += S_i
                score_sum[mid_j] += S_j
                expected_sum[mid_i] += E_i
                expected_sum[mid_j] += E_j

        # Update each model's ELO rating in the database
        for mid in model_ids:
            delta = (K / (n - 1)) * (score_sum[mid] - expected_sum[mid]) if (n > 1) else 0
            new_rating = ratings[mid] + delta

            cursor.execute("""
                UPDATE models
                SET elo_rating = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (new_rating, mid))

            print(f"Updated ELO for {names[mid]}: {ratings[mid]:.2f} -> {new_rating:.2f} (delta: {delta:+.2f})")

        conn.commit()

    except Exception as e:
        print(f"Error updating ELO ratings for game {game_id}: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def update_model_aggregates(game_id: str) -> None:
    """
    Update model aggregate statistics (wins, losses, ties, apples_eaten, games_played)
    for all participants in a game.

    Args:
        game_id: The game identifier to process
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Get all participants for this game
        cursor.execute("""
            SELECT
                gp.model_id,
                gp.result,
                gp.score,
                m.name
            FROM game_participants gp
            JOIN models m ON gp.model_id = m.id
            WHERE gp.game_id = %s
        """, (game_id,))

        participants = cursor.fetchall()

        for participant in participants:
            model_id = participant['model_id']
            result = participant['result']
            score = participant['score']
            name = participant['name']
            # Update win/loss/tie counts
            win_delta = 1 if result == 'won' else 0
            loss_delta = 1 if result == 'lost' else 0
            tie_delta = 1 if result == 'tied' else 0

            cursor.execute("""
                UPDATE models
                SET wins = wins + %s,
                    losses = losses + %s,
                    ties = ties + %s,
                    apples_eaten = apples_eaten + %s,
                    games_played = games_played + 1,
                    last_played_at = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                win_delta,
                loss_delta,
                tie_delta,
                score,  # apples_eaten = score
                datetime.now().isoformat(),
                model_id
            ))

            print(f"Updated aggregates for {name}: +{score} apples, result={result}")

        conn.commit()

    except Exception as e:
        print(f"Error updating aggregates for game {game_id}: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
