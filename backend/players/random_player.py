"""
Random player implementation - picks random safe moves.
"""

import random
from typing import List

from domain.constants import UP, DOWN, LEFT, RIGHT, VALID_MOVES
from domain.game_state import GameState
from .base import Player


class RandomPlayer(Player):
    """
    A random AI that picks a valid direction that avoids walls and self-collisions.
    """

    def get_move(self, game_state: GameState) -> str:
        snake_positions = game_state.snake_positions[self.snake_id]
        head_x, head_y = snake_positions[0]

        # Calculate all possible next positions
        possible_moves = {
            UP:    (head_x, head_y + 1),  # Up => y + 1
            DOWN:  (head_x, head_y - 1),  # Down => y - 1
            LEFT:  (head_x - 1, head_y),
            RIGHT: (head_x + 1, head_y)
        }

        # Filter out moves that:
        # 1. Hit walls
        # 2. Hit own body (except tail, which will move)
        valid_moves: List[str] = []
        for move, (new_x, new_y) in possible_moves.items():
            # Check wall collisions
            if (new_x < 0 or new_x >= game_state.width or
                new_y < 0 or new_y >= game_state.height):
                continue

            # Check self collisions (excluding tail which will move)
            if (new_x, new_y) in snake_positions[:-1]:
                continue

            valid_moves.append(move)

        # If no valid moves, just return a random move (we'll die anyway)
        if not valid_moves:
            return random.choice(list(VALID_MOVES))

        return random.choice(valid_moves)
