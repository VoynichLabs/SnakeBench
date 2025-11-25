"""
Repository pattern implementations for data access.

This module provides a clean abstraction over database operations
with proper connection management and error handling.
"""

from .base import BaseRepository
from .game_repository import GameRepository
from .model_repository import ModelRepository

__all__ = ['BaseRepository', 'GameRepository', 'ModelRepository']
