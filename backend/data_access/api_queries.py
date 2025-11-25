"""
API query functions for retrieving data from the database.

These functions provide the database layer for the Flask API endpoints.
They delegate to the repository classes for actual database operations.
"""

from typing import List, Dict, Any, Optional

from .repositories import GameRepository, ModelRepository

# Repository instances
_game_repo = GameRepository()
_model_repo = ModelRepository()


def get_all_models(active_only: bool = False) -> List[Dict[str, Any]]:
    """
    Retrieve all models with their statistics, sorted by ELO rating.

    Args:
        active_only: If True, only return active models

    Returns:
        List of model dictionaries with stats
    """
    return _model_repo.get_all(active_only=active_only)


def get_model_by_name(model_name: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a single model by name with its statistics.

    Args:
        model_name: The model name to look up

    Returns:
        Model dictionary with stats, or None if not found
    """
    return _model_repo.get_by_name(model_name)


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
    return _game_repo.get_games(limit=limit, offset=offset, sort_by=sort_by)


def get_game_by_id(game_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a single game by ID with participant information.

    Args:
        game_id: The game identifier

    Returns:
        Game dictionary with participant information, or None if not found
    """
    game = _game_repo.get_by_id(game_id)
    if game is None:
        return None

    # Get participants for backward compatibility format
    participants = _game_repo.get_participants(game_id)
    game['participants'] = [
        {
            'model_name': p['model_name'],
            'provider': None,  # Not included in get_participants
            'player_slot': p['player_slot'],
            'score': p['score'],
            'result': p['result'],
            'death_round': p['death_round'],
            'death_reason': p['death_reason']
        }
        for p in participants
    ]

    return game


def get_total_games_count() -> int:
    """
    Get the total number of games in the database.

    Returns:
        Total count of games
    """
    return _game_repo.get_total_count()


def get_top_apples_game() -> Optional[Dict[str, Any]]:
    """
    Retrieve the game with the highest combined apples eaten (total_score).

    Returns:
        Game dictionary with minimal metadata, or None if no games exist
    """
    return _game_repo.get_top_apples_game()
