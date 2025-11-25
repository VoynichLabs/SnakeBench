"""
Snake entity for the game engine.
"""

from collections import deque
from typing import List, Tuple, Optional


class Snake:
    """
    Represents a snake on the board.

    Attributes:
        positions: deque of (x, y) from head at index 0 to tail at the end
        alive: whether this snake is still alive
        death_reason: e.g., 'wall', 'self', 'collision'
        death_round: The round number when the snake died
    """

    def __init__(self, positions: List[Tuple[int, int]]):
        self.positions = deque(positions)
        self.alive = True
        self.death_reason: Optional[str] = None
        self.death_round: Optional[int] = None

    @property
    def head(self) -> Tuple[int, int]:
        """Return the head position (first element)."""
        return self.positions[0]
