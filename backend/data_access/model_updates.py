"""
Model statistics update functions including ELO ratings and aggregates.

These functions delegate to the ModelRepository for actual database operations.
"""

from .repositories import ModelRepository
from .repositories.model_repository import get_pair_result, expected_score

# Repository instance
_model_repo = ModelRepository()

# Re-export ELO helper functions for backward compatibility
__all__ = [
    'get_pair_result',
    'expected_score',
    'update_elo_ratings',
    'update_model_aggregates',
    'update_trueskill_ratings',
]


def update_elo_ratings(game_id: str) -> None:
    """
    Update ELO ratings for all participants in a game using pairwise comparisons.

    This implements the same algorithm as elo_tracker.py process_game() function,
    computing pairwise expected/actual scores and updating ratings incrementally.

    Args:
        game_id: The game identifier to process
    """
    _model_repo.update_elo_ratings_for_game(game_id)


def update_model_aggregates(game_id: str) -> None:
    """
    Update model aggregate statistics (wins, losses, ties, apples_eaten, games_played)
    for all participants in a game.

    Args:
        game_id: The game identifier to process
    """
    _model_repo.update_aggregates_for_game(game_id)


def update_trueskill_ratings(game_id: str) -> None:
    """
    Update TrueSkill ratings for all participants in a game.

    Args:
        game_id: The game identifier to process
    """
    # Import here to avoid circular import during module initialization
    from services.trueskill_engine import trueskill_engine
    trueskill_engine.rate_game(game_id)
