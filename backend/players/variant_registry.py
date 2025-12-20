"""
Author: Cascade
Date: 2025-12-20
PURPOSE: Registry for LLM player variants.
         Maps variant keys (e.g., 'default', 'A', 'B') to player classes.
         Extensible: to add a new variant, create llm_player_x.py with class LLMPlayerX,
         import it here, and add an entry to PLAYER_VARIANTS.

SRP/DRY check: Pass - single responsibility is mapping variant keys to player classes.
"""

from typing import Dict, Type, Optional
from .base import Player


# Lazy imports to avoid circular dependencies and allow graceful fallback
def _get_default_player() -> Type[Player]:
    from .llm_player import LLMPlayer
    return LLMPlayer


def _get_player_a() -> Type[Player]:
    from .llm_player_a import LLMPlayerA
    return LLMPlayerA


# Registry: maps variant key -> callable that returns the player class
# Using callables for lazy loading
PLAYER_VARIANT_LOADERS: Dict[str, callable] = {
    "default": _get_default_player,
    "A": _get_player_a,
    # Future variants:
    # "B": _get_player_b,
    # "C": _get_player_c,
}

# Canonical list of available variant keys (for API exposure)
AVAILABLE_VARIANTS = list(PLAYER_VARIANT_LOADERS.keys())


def get_player_class(variant_key: Optional[str] = None) -> Type[Player]:
    """
    Get the player class for a given variant key.

    Args:
        variant_key: One of 'default', 'A', 'B', etc. If None or empty, returns default.

    Returns:
        The player class (subclass of Player).

    Raises:
        ValueError: If variant_key is not recognized.
    """
    if not variant_key or variant_key.strip() == "":
        variant_key = "default"

    variant_key = variant_key.strip()

    if variant_key not in PLAYER_VARIANT_LOADERS:
        available = ", ".join(AVAILABLE_VARIANTS)
        raise ValueError(
            f"Unknown player variant '{variant_key}'. Available variants: {available}"
        )

    return PLAYER_VARIANT_LOADERS[variant_key]()


def list_variants() -> list:
    """
    Return metadata about all available player variants.

    Returns:
        List of dicts with 'key' and 'description' for each variant.
    """
    return [
        {"key": "default", "description": "Baseline LLM player (original SnakeBench prompt)"},
        {"key": "A", "description": "Variant A: Tactical cheat-sheet prompt with structured decision checklist"},
        # Future variants:
        # {"key": "B", "description": "Variant B: ..."},
    ]
