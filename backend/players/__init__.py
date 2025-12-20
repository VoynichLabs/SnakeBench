"""
Player implementations for LLMSnake.

This module contains the player abstractions and implementations
that control snake movement decisions.

Updated: 2025-12-20 - Added player variant system for A/B testing different prompts.
"""

from .base import Player
from .random_player import RandomPlayer
from .llm_player import LLMPlayer
from .llm_player_a import LLMPlayerA
from .variant_registry import get_player_class, list_variants, AVAILABLE_VARIANTS

__all__ = [
    'Player',
    'RandomPlayer',
    'LLMPlayer',
    'LLMPlayerA',
    'get_player_class',
    'list_variants',
    'AVAILABLE_VARIANTS',
]
