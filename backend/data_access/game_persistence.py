"""
Game persistence functions for inserting game data into the database.
"""

import psycopg2
from datetime import datetime
from typing import Dict, Any, List
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_postgres import get_connection


def insert_game(
    game_id: str,
    start_time: datetime,
    end_time: datetime,
    rounds: int,
    replay_path: str,
    board_width: int,
    board_height: int,
    num_apples: int,
    total_score: int,
    total_cost: float = 0.0,
    game_type: str = 'ladder'
) -> None:
    """
    Insert a game record into the games table.

    Args:
        game_id: Unique game identifier (UUID)
        start_time: Game start timestamp
        end_time: Game end timestamp
        rounds: Number of rounds played
        replay_path: Path to the JSON replay file
        board_width: Width of the game board
        board_height: Height of the game board
        num_apples: Number of apples in the game
        total_score: Combined score of all players
        total_cost: Total cost of LLM API calls for this game
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO games (
                id, start_time, end_time, rounds, replay_path,
                board_width, board_height, num_apples, total_score, total_cost, game_type
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            game_id,
            start_time.isoformat() if isinstance(start_time, datetime) else start_time,
            end_time.isoformat() if isinstance(end_time, datetime) else end_time,
            rounds,
            replay_path,
            board_width,
            board_height,
            num_apples,
            total_score,
            total_cost,
            game_type
        ))

        conn.commit()
        print(f"Inserted game {game_id} into database (cost: ${total_cost:.6f})")

    except psycopg2.IntegrityError as e:
        print(f"Game {game_id} already exists in database: {e}")
        conn.rollback()
    except Exception as e:
        print(f"Error inserting game {game_id}: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_game_participants(
    game_id: str,
    participants: List[Dict[str, Any]]
) -> None:
    """
    Insert game participant records into the game_participants table.

    Args:
        game_id: The game identifier
        participants: List of participant dictionaries with keys:
            - model_name: Name of the model (must exist in models table)
            - player_slot: Player slot number (0, 1, etc.)
            - score: Final score for this player
            - result: Game result ('won', 'lost', 'tied')
            - death_round: Round number when player died (optional)
            - death_reason: Reason for death (optional)
            - cost: Total cost for this player (optional)
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        for participant in participants:
            # Get model_id from model name
            cursor.execute(
                "SELECT id FROM models WHERE name = %s",
                (participant['model_name'],)
            )
            row = cursor.fetchone()

            if row is None:
                print(f"Warning: Model '{participant['model_name']}' not found in database. Skipping participant.")
                continue

            model_id = row['id']

            # Insert or update participant record (handles live games that already have placeholder records)
            cursor.execute("""
                INSERT INTO game_participants (
                    game_id, model_id, player_slot, score, result,
                    death_round, death_reason, cost
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (game_id, player_slot)
                DO UPDATE SET
                    score = EXCLUDED.score,
                    result = EXCLUDED.result,
                    death_round = EXCLUDED.death_round,
                    death_reason = EXCLUDED.death_reason,
                    cost = EXCLUDED.cost
            """, (
                game_id,
                model_id,
                participant['player_slot'],
                participant['score'],
                participant['result'],
                participant.get('death_round'),
                participant.get('death_reason'),
                participant.get('cost', 0.0)
            ))

        conn.commit()
        print(f"Inserted {len(participants)} participants for game {game_id}")

    except Exception as e:
        print(f"Error inserting participants for game {game_id}: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
