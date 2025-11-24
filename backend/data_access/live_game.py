"""
Live game state management functions.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_postgres import get_connection


def insert_initial_game(
    game_id: str,
    start_time: datetime,
    board_width: int,
    board_height: int,
    num_apples: int,
    status: str = 'in_progress',
    game_type: str = 'ladder'
) -> None:
    """
    Insert initial game record when game starts.

    Args:
        game_id: Unique game identifier (UUID)
        start_time: Game start timestamp
        board_width: Width of the game board
        board_height: Height of the game board
        num_apples: Number of apples in the game
        status: Initial status (default 'in_progress')
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO games (
                id, status, start_time, board_width, board_height, num_apples, game_type
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            game_id,
            status,
            start_time.isoformat() if isinstance(start_time, datetime) else start_time,
            board_width,
            board_height,
            num_apples,
            game_type
        ))

        conn.commit()
        print(f"Inserted initial game record {game_id}")

    except Exception as e:
        print(f"Error inserting initial game {game_id}: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_initial_participants(
    game_id: str,
    participants: List[Dict[str, Any]]
) -> None:
    """
    Insert initial game participant records when game starts.
    This is called before the game runs to enable live game model name display.

    Args:
        game_id: The game identifier
        participants: List of participant dictionaries with keys:
            - model_name: Name of the model (must exist in models table)
            - player_slot: Player slot number (0, 1, etc.)
            - opponent_rank_at_match: Rank index of this model at match time (optional, for evaluation games)
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

            # Insert participant record with placeholder values
            cursor.execute("""
                INSERT INTO game_participants (
                    game_id, model_id, player_slot, score, result, opponent_rank_at_match
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                game_id,
                model_id,
                participant['player_slot'],
                0,  # Placeholder score, will be updated at end
                'tied',  # Temporary placeholder result, will be updated at end
                participant.get('opponent_rank_at_match')  # Store rank if provided (for evaluation games)
            ))

        conn.commit()
        print(f"Inserted {len(participants)} initial participants for game {game_id}")

    except Exception as e:
        print(f"Error inserting initial participants for game {game_id}: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def update_game_state(
    game_id: str,
    current_state: Dict[str, Any],
    rounds: int
) -> None:
    """
    Update the current state of a live game.

    Args:
        game_id: The game identifier
        current_state: Dictionary containing the current game state
            (round_number, snake_positions, scores, alive_status, apples, board_state)
        rounds: Current round number
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE games
            SET current_state = %s,
                rounds = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (
            json.dumps(current_state),
            rounds,
            game_id
        ))

        conn.commit()

    except Exception as e:
        print(f"Error updating game state for {game_id}: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def complete_game(
    game_id: str,
    end_time: datetime,
    rounds: int,
    replay_path: str,
    total_score: int,
    total_cost: float = 0.0
) -> None:
    """
    Mark a game as completed and update final stats.

    Args:
        game_id: The game identifier
        end_time: Game end timestamp
        rounds: Final number of rounds
        replay_path: Path to the JSON replay file
        total_score: Combined score of all players
        total_cost: Total cost of LLM API calls
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE games
            SET status = 'completed',
                end_time = %s,
                updated_at = %s,
                rounds = %s,
                replay_path = %s,
                total_score = %s,
                total_cost = %s,
                current_state = NULL
            WHERE id = %s
        """, (
            end_time.isoformat() if isinstance(end_time, datetime) else end_time,
            end_time.isoformat() if isinstance(end_time, datetime) else end_time,
            rounds,
            replay_path,
            total_score,
            total_cost,
            game_id
        ))

        conn.commit()
        print(f"Marked game {game_id} as completed")

    except Exception as e:
        print(f"Error completing game {game_id}: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def get_live_games() -> List[Dict[str, Any]]:
    """
    Get all games currently in progress.

    Returns:
        List of game dictionaries with basic info and current state
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                g.id,
                g.status,
                g.start_time,
                g.rounds,
                g.board_width,
                g.board_height,
                g.num_apples,
                g.current_state
            FROM games g
            WHERE g.status = 'in_progress'
            ORDER BY g.start_time DESC
        """)

        rows = cursor.fetchall()
        games = []
        for row in rows:
            # Get model names for this game
            cursor.execute("""
                SELECT gp.player_slot, m.name
                FROM game_participants gp
                JOIN models m ON gp.model_id = m.id
                WHERE gp.game_id = %s
                ORDER BY gp.player_slot
            """, (row['id'],))

            model_rows = cursor.fetchall()
            models = {str(model_row['player_slot']): model_row['name'] for model_row in model_rows}

            game = {
                'id': row['id'],
                'status': row['status'],
                'start_time': row['start_time'],
                'rounds': row['rounds'],
                'board_width': row['board_width'],
                'board_height': row['board_height'],
                'num_apples': row['num_apples'],
                'current_state': json.loads(row['current_state']) if row['current_state'] else None,
                'models': models
            }
            games.append(game)

        return games

    except Exception as e:
        print(f"Error fetching live games: {e}")
        raise
    finally:
        conn.close()


def get_game_state(game_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the current state of a specific game.

    Args:
        game_id: The game identifier

    Returns:
        Dictionary with game info and current state, or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                g.id,
                g.status,
                g.start_time,
                g.rounds,
                g.board_width,
                g.board_height,
                g.num_apples,
                g.current_state,
                g.total_score,
                g.total_cost
            FROM games g
            WHERE g.id = %s
        """, (game_id,))

        row = cursor.fetchone()
        if row is None:
            return None

        # Get model names for this game
        cursor.execute("""
            SELECT gp.player_slot, m.name
            FROM game_participants gp
            JOIN models m ON gp.model_id = m.id
            WHERE gp.game_id = %s
            ORDER BY gp.player_slot
        """, (game_id,))

        model_rows = cursor.fetchall()
        models = {str(model_row['player_slot']): model_row['name'] for model_row in model_rows}

        return {
            'id': row['id'],
            'status': row['status'],
            'start_time': row['start_time'],
            'rounds': row['rounds'],
            'board_width': row['board_width'],
            'board_height': row['board_height'],
            'num_apples': row['num_apples'],
            'current_state': json.loads(row['current_state']) if row['current_state'] else None,
            'total_score': row['total_score'],
            'total_cost': row['total_cost'],
            'models': models
        }

    except Exception as e:
        print(f"Error fetching game state for {game_id}: {e}")
        raise
    finally:
        conn.close()
