"""
Data access layer for LLMSnake database operations.

This module provides functions for inserting games, updating model statistics,
and managing ELO ratings in an event-driven manner.
"""

from .game_persistence import insert_game, insert_game_participants
from .model_updates import update_model_aggregates, update_elo_ratings
from .live_game import (
    insert_initial_game,
    insert_initial_participants,
    update_game_state,
    complete_game,
    get_live_games,
    get_game_state
)

__all__ = [
    'insert_game',
    'insert_game_participants',
    'update_model_aggregates',
    'update_elo_ratings',
    'insert_initial_game',
    'insert_initial_participants',
    'update_game_state',
    'complete_game',
    'get_live_games',
    'get_game_state',
]
