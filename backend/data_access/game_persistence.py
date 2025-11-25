"""
Game persistence functions for inserting game data into the database.

These functions delegate to the GameRepository for actual database operations.
"""

from datetime import datetime
from typing import Dict, Any, List

from .repositories import GameRepository

# Repository instance
_game_repo = GameRepository()


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
        game_type: Type of game ('ladder', 'evaluation', etc.)
    """
    _game_repo.insert_game(
        game_id=game_id,
        start_time=start_time,
        end_time=end_time,
        rounds=rounds,
        replay_path=replay_path,
        board_width=board_width,
        board_height=board_height,
        num_apples=num_apples,
        total_score=total_score,
        total_cost=total_cost,
        game_type=game_type
    )


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
    _game_repo.insert_participants(game_id, participants)
