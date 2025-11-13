"""
Recompute ELO ratings and aggregates from all games in the database.

This script processes all games in chronological order and updates model
ratings and statistics using the same algorithm as elo_tracker.py.
"""

import sqlite3
from typing import Dict, List
from database import get_connection, get_database_path

# ELO parameters (matching elo_tracker.py)
K = 32
INITIAL_RATING = 1500.0

# Result rankings
RESULT_RANK = {"won": 2, "tied": 1, "lost": 0}


def get_pair_result(result_i: str, result_j: str) -> tuple:
    """
    Given the result strings for two players, return a tuple (S_i, S_j)
    representing the head-to-head score:
      - S = 1 means win, 0 means loss, 0.5 means tie.
    """
    rank_i = RESULT_RANK.get(result_i, 1)
    rank_j = RESULT_RANK.get(result_j, 1)

    if rank_i > rank_j:
        return 1.0, 0.0
    elif rank_i < rank_j:
        return 0.0, 1.0
    else:
        return 0.5, 0.5


def expected_score(rating_i: float, rating_j: float) -> float:
    """Compute the expected score for player i vs. player j."""
    return 1.0 / (1.0 + 10 ** ((rating_j - rating_i) / 400.0))


def process_game(participants: List[Dict], ratings: Dict, stats: Dict) -> None:
    """
    Process one game and update ratings and stats.

    Args:
        participants: List of participant dicts with model_id, result, score
        ratings: Dict mapping model_id to current ELO rating
        stats: Dict mapping model_id to stats (wins/losses/ties/apples)
    """
    n = len(participants)

    # Ensure all models exist in our tracking dicts
    for p in participants:
        model_id = p['model_id']
        if model_id not in ratings:
            ratings[model_id] = INITIAL_RATING
        if model_id not in stats:
            stats[model_id] = {
                'wins': 0,
                'losses': 0,
                'ties': 0,
                'apples_eaten': 0,
                'games_played': 0
            }

    # Accumulate actual/expected scores for each model
    score_sum = {p['model_id']: 0.0 for p in participants}
    expected_sum = {p['model_id']: 0.0 for p in participants}

    # Loop over all unordered pairs of players
    for i in range(n):
        for j in range(i + 1, n):
            p_i = participants[i]
            p_j = participants[j]

            model_i = p_i['model_id']
            model_j = p_j['model_id']

            # Determine head-to-head result
            S_i, S_j = get_pair_result(p_i['result'], p_j['result'])

            # Compute expected scores from current ratings
            R_i = ratings[model_i]
            R_j = ratings[model_j]
            E_i = expected_score(R_i, R_j)
            E_j = expected_score(R_j, R_i)

            # Accumulate results
            score_sum[model_i] += S_i
            score_sum[model_j] += S_j
            expected_sum[model_i] += E_i
            expected_sum[model_j] += E_j

    # Update each player's rating
    for p in participants:
        model_id = p['model_id']

        # Update ELO rating
        if n > 1:
            delta = (K / (n - 1)) * (score_sum[model_id] - expected_sum[model_id])
            ratings[model_id] += delta

        # Update stats
        result = p['result']
        if result == 'won':
            stats[model_id]['wins'] += 1
        elif result == 'lost':
            stats[model_id]['losses'] += 1
        else:
            stats[model_id]['ties'] += 1

        stats[model_id]['apples_eaten'] += p['score']
        stats[model_id]['games_played'] += 1


def recompute_elo():
    """
    Recompute ELO ratings and aggregates from scratch using all games.
    """
    print(f"Database path: {get_database_path()}\n")

    conn = get_connection()
    cursor = conn.cursor()

    # Initialize tracking dictionaries
    ratings = {}  # model_id -> current ELO rating
    stats = {}    # model_id -> {wins, losses, ties, apples_eaten, games_played}

    try:
        # Get all games in chronological order
        cursor.execute("""
            SELECT id, start_time
            FROM games
            ORDER BY start_time ASC
        """)
        games = cursor.fetchall()

        print(f"Processing {len(games)} games in chronological order...\n")

        processed = 0
        for game_row in games:
            game_id = game_row[0]

            # Get all participants for this game
            cursor.execute("""
                SELECT model_id, player_slot, score, result, death_round, death_reason
                FROM game_participants
                WHERE game_id = ?
                ORDER BY player_slot
            """, (game_id,))

            participants = []
            for p_row in cursor.fetchall():
                participants.append({
                    'model_id': p_row[0],
                    'player_slot': p_row[1],
                    'score': p_row[2],
                    'result': p_row[3],
                    'death_round': p_row[4],
                    'death_reason': p_row[5],
                })

            # Process this game
            if participants:
                process_game(participants, ratings, stats)
                processed += 1

                if processed % 500 == 0:
                    print(f"  Processed {processed}/{len(games)} games")

        print(f"\nProcessed all {processed} games\n")

        # Now update the models table with computed ratings and stats
        print("Updating models table with computed ratings and stats...")

        updated = 0
        for model_id, rating in ratings.items():
            model_stats = stats.get(model_id, {})

            cursor.execute("""
                UPDATE models
                SET elo_rating = ?,
                    wins = ?,
                    losses = ?,
                    ties = ?,
                    apples_eaten = ?,
                    games_played = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                rating,
                model_stats.get('wins', 0),
                model_stats.get('losses', 0),
                model_stats.get('ties', 0),
                model_stats.get('apples_eaten', 0),
                model_stats.get('games_played', 0),
                model_id
            ))
            updated += 1

        conn.commit()

        print(f"Updated {updated} models\n")

        # Show top 10 models by ELO
        print("Top 10 models by ELO rating:")
        cursor.execute("""
            SELECT name, elo_rating, wins, losses, ties, games_played
            FROM models
            WHERE games_played > 0
            ORDER BY elo_rating DESC
            LIMIT 10
        """)

        print("\n{:<50} {:>10} {:>6} {:>6} {:>6} {:>8}".format(
            "Model", "ELO", "Wins", "Loss", "Ties", "Games"
        ))
        print("-" * 90)

        for row in cursor.fetchall():
            name = row[0]
            elo = row[1]
            wins = row[2]
            losses = row[3]
            ties = row[4]
            games = row[5]

            print("{:<50} {:>10.1f} {:>6} {:>6} {:>6} {:>8}".format(
                name[:50], elo, wins, losses, ties, games
            ))

    except Exception as e:
        conn.rollback()
        print(f"Error recomputing ELO: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    recompute_elo()
