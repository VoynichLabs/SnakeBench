"""
Live game state management functions.

These functions delegate to the GameRepository for actual database operations.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional

from .repositories import GameRepository

# Repository instance
_game_repo = GameRepository()


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
        game_type: Type of game
    """
    _game_repo.insert_initial_game(
        game_id=game_id,
        start_time=start_time,
        board_width=board_width,
        board_height=board_height,
        num_apples=num_apples,
        status=status,
        game_type=game_type
    )


def insert_initial_participants(
    game_id: str,
    participants: List[Dict[str, Any]]
) -> None:
    """
    Insert initial game participant records when game starts.

    Args:
        game_id: The game identifier
        participants: List of participant dictionaries with keys:
            - model_name: Name of the model
            - player_slot: Player slot number
            - opponent_rank_at_match: Rank index (optional)
    """
    _game_repo.insert_initial_participants(game_id, participants)


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
        rounds: Current round number
    """
    _game_repo.update_game_state(game_id, current_state, rounds)


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
    _game_repo.complete_game(
        game_id=game_id,
        end_time=end_time,
        rounds=rounds,
        replay_path=replay_path,
        total_score=total_score,
        total_cost=total_cost
    )


def get_live_games() -> List[Dict[str, Any]]:
    """
    Get all games currently in progress.

    Returns:
        List of game dictionaries with basic info and current state
    """
    return _game_repo.get_live_games()


def get_game_state(game_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the current state of a specific game.

    Args:
        game_id: The game identifier

    Returns:
        Dictionary with game info and current state, or None if not found
    """
    return _game_repo.get_game_state(game_id)
