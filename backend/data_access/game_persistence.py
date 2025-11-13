"""
Game persistence functions for inserting game data into the database.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, List
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection


def insert_game(
    game_id: str,
    start_time: datetime,
    end_time: datetime,
    rounds: int,
    replay_path: str,
    board_width: int,
    board_height: int,
    num_apples: int,
    total_score: int
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
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO games (
                id, start_time, end_time, rounds, replay_path,
                board_width, board_height, num_apples, total_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            game_id,
            start_time.isoformat() if isinstance(start_time, datetime) else start_time,
            end_time.isoformat() if isinstance(end_time, datetime) else end_time,
            rounds,
            replay_path,
            board_width,
            board_height,
            num_apples,
            total_score
        ))

        conn.commit()
        print(f"Inserted game {game_id} into database")

    except sqlite3.IntegrityError as e:
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
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        for participant in participants:
            # Get model_id from model name
            cursor.execute(
                "SELECT id FROM models WHERE name = ?",
                (participant['model_name'],)
            )
            row = cursor.fetchone()

            if row is None:
                print(f"Warning: Model '{participant['model_name']}' not found in database. Skipping participant.")
                continue

            model_id = row[0]

            # Insert participant record
            cursor.execute("""
                INSERT INTO game_participants (
                    game_id, model_id, player_slot, score, result,
                    death_round, death_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id,
                model_id,
                participant['player_slot'],
                participant['score'],
                participant['result'],
                participant.get('death_round'),
                participant.get('death_reason')
            ))

        conn.commit()
        print(f"Inserted {len(participants)} participants for game {game_id}")

    except Exception as e:
        print(f"Error inserting participants for game {game_id}: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
