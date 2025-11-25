"""
Base player interface for the game engine.
"""

from domain.game_state import GameState


class Player:
    """
    Base class/interface for player logic.

    Each player is responsible for returning a move for its snake_id
    given the current game state.
    """

    def __init__(self, snake_id: str):
        self.snake_id = snake_id

    def get_move(self, game_state: GameState) -> str:
        """
        Return a move direction given the current game state.

        Args:
            game_state: Current state of the game

        Returns:
            One of: "UP", "DOWN", "LEFT", "RIGHT"
        """
        raise NotImplementedError
