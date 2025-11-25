"""
Domain entities for LLMSnake game engine.

This module contains the core game entities that are independent of
infrastructure concerns (database, API calls, etc.).
"""

from .constants import UP, DOWN, LEFT, RIGHT, VALID_MOVES, APPLE_TARGET
from .snake import Snake
from .game_state import GameState

__all__ = [
    'UP', 'DOWN', 'LEFT', 'RIGHT', 'VALID_MOVES', 'APPLE_TARGET',
    'Snake',
    'GameState',
]
