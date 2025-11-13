"""
API query functions for retrieving data from the database.

These functions provide the database layer for the Flask API endpoints,
replacing direct JSON file reads with database queries.
"""

import sqlite3
from typing import List, Dict, Any, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection


def get_all_models(active_only: bool = False) -> List[Dict[str, Any]]:
    """
    Retrieve all models with their statistics, sorted by ELO rating.

    Args:
        active_only: If True, only return active models

    Returns:
        List of model dictionaries with stats
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        query = """
            SELECT
                id,
                name,
                provider,
                model_slug,
                is_active,
                test_status,
                elo_rating,
                wins,
                losses,
                ties,
                apples_eaten,
                games_played,
                pricing_input_per_m,
                pricing_output_per_m,
                max_completion_tokens,
                last_played_at,
                discovered_at
            FROM models
        """

        if active_only:
            query += " WHERE is_active = 1"

        query += " ORDER BY elo_rating DESC"

        cursor.execute(query)
        rows = cursor.fetchall()

        models = []
        for row in rows:
            models.append({
                'id': row[0],
                'name': row[1],
                'provider': row[2],
                'model_slug': row[3],
                'is_active': bool(row[4]),
                'test_status': row[5],
                'elo_rating': row[6],
                'wins': row[7],
                'losses': row[8],
                'ties': row[9],
                'apples_eaten': row[10],
                'games_played': row[11],
                'pricing_input_per_m': row[12],
                'pricing_output_per_m': row[13],
                'max_completion_tokens': row[14],
                'last_played_at': row[15],
                'discovered_at': row[16]
            })

        return models

    finally:
        conn.close()


def get_model_by_name(model_name: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a single model by name with its statistics.

    Args:
        model_name: The model name to look up

    Returns:
        Model dictionary with stats, or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                id,
                name,
                provider,
                model_slug,
                is_active,
                test_status,
                elo_rating,
                wins,
                losses,
                ties,
                apples_eaten,
                games_played,
                pricing_input_per_m,
                pricing_output_per_m,
                max_completion_tokens,
                last_played_at,
                discovered_at
            FROM models
            WHERE name = ?
        """, (model_name,))

        row = cursor.fetchone()

        if row is None:
            return None

        return {
            'id': row[0],
            'name': row[1],
            'provider': row[2],
            'model_slug': row[3],
            'is_active': bool(row[4]),
            'test_status': row[5],
            'elo_rating': row[6],
            'wins': row[7],
            'losses': row[8],
            'ties': row[9],
            'apples_eaten': row[10],
            'games_played': row[11],
            'pricing_input_per_m': row[12],
            'pricing_output_per_m': row[13],
            'max_completion_tokens': row[14],
            'last_played_at': row[15],
            'discovered_at': row[16]
        }

    finally:
        conn.close()


def get_games(
    limit: int = 10,
    offset: int = 0,
    sort_by: str = "start_time"
) -> List[Dict[str, Any]]:
    """
    Retrieve games with participant information.

    Args:
        limit: Maximum number of games to return
        offset: Number of games to skip (for pagination)
        sort_by: Field to sort by ('start_time', 'total_score', 'rounds')

    Returns:
        List of game dictionaries with participant information
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Validate sort_by to prevent SQL injection
        valid_sort_fields = {
            'start_time': 'g.start_time DESC',
            'total_score': 'g.total_score DESC',
            'rounds': 'g.rounds DESC'
        }

        order_clause = valid_sort_fields.get(sort_by, 'g.start_time DESC')

        # Get games
        cursor.execute(f"""
            SELECT
                g.id,
                g.start_time,
                g.end_time,
                g.rounds,
                g.replay_path,
                g.board_width,
                g.board_height,
                g.num_apples,
                g.total_score,
                g.created_at
            FROM games g
            ORDER BY {order_clause}
            LIMIT ? OFFSET ?
        """, (limit, offset))

        games = []
        for row in cursor.fetchall():
            game = {
                'id': row[0],
                'start_time': row[1],
                'end_time': row[2],
                'rounds': row[3],
                'replay_path': row[4],
                'board_width': row[5],
                'board_height': row[6],
                'num_apples': row[7],
                'total_score': row[8],
                'created_at': row[9],
                'participants': []
            }

            # Get participants for this game
            cursor.execute("""
                SELECT
                    m.name,
                    m.provider,
                    gp.player_slot,
                    gp.score,
                    gp.result,
                    gp.death_round,
                    gp.death_reason
                FROM game_participants gp
                JOIN models m ON gp.model_id = m.id
                WHERE gp.game_id = ?
                ORDER BY gp.player_slot
            """, (game['id'],))

            for participant_row in cursor.fetchall():
                game['participants'].append({
                    'model_name': participant_row[0],
                    'provider': participant_row[1],
                    'player_slot': participant_row[2],
                    'score': participant_row[3],
                    'result': participant_row[4],
                    'death_round': participant_row[5],
                    'death_reason': participant_row[6]
                })

            games.append(game)

        return games

    finally:
        conn.close()


def get_game_by_id(game_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a single game by ID with participant information.

    Args:
        game_id: The game identifier

    Returns:
        Game dictionary with participant information, or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                id,
                start_time,
                end_time,
                rounds,
                replay_path,
                board_width,
                board_height,
                num_apples,
                total_score,
                created_at
            FROM games
            WHERE id = ?
        """, (game_id,))

        row = cursor.fetchone()

        if row is None:
            return None

        game = {
            'id': row[0],
            'start_time': row[1],
            'end_time': row[2],
            'rounds': row[3],
            'replay_path': row[4],
            'board_width': row[5],
            'board_height': row[6],
            'num_apples': row[7],
            'total_score': row[8],
            'created_at': row[9],
            'participants': []
        }

        # Get participants
        cursor.execute("""
            SELECT
                m.name,
                m.provider,
                gp.player_slot,
                gp.score,
                gp.result,
                gp.death_round,
                gp.death_reason
            FROM game_participants gp
            JOIN models m ON gp.model_id = m.id
            WHERE gp.game_id = ?
            ORDER BY gp.player_slot
        """, (game_id,))

        for participant_row in cursor.fetchall():
            game['participants'].append({
                'model_name': participant_row[0],
                'provider': participant_row[1],
                'player_slot': participant_row[2],
                'score': participant_row[3],
                'result': participant_row[4],
                'death_round': participant_row[5],
                'death_reason': participant_row[6]
            })

        return game

    finally:
        conn.close()


def get_total_games_count() -> int:
    """
    Get the total number of games in the database.

    Returns:
        Total count of games
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM games")
        count = cursor.fetchone()[0]
        return count

    finally:
        conn.close()
