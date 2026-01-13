# Author: Cascade (ChatGPT)
# Date: 2026-01-12
# PURPOSE: Centralize LLMSnake movement and victory constants so engine, prompts, and analytics share a single source of truth for rule enforcement.
# SRP/DRY check: Pass — verified existing consumers (SnakeGame, LLM prompts) already reference these constants without duplicating logic.

"""
Game constants for LLMSnake.
"""

# Movement directions
UP = "UP"
DOWN = "DOWN"
LEFT = "LEFT"
RIGHT = "RIGHT"
VALID_MOVES = {UP, DOWN, LEFT, RIGHT}

# Game settings
APPLE_TARGET = 30
