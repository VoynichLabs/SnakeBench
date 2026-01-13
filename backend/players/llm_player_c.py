# LLM-based player implementation - Variant C with minimal prompt (rules only, no thinking).

# Author: Cascade
# Date: 2026-01-12
# PURPOSE: LLM player variant with minimal prompt that only provides rules and requires a single-word response
# SRP/DRY check: Pass - Extends base Player class, reuses provider abstraction, maintains same move logic as llm_player.py with only prompt changes

import random
from typing import Dict, Any, Optional

from domain.constants import UP, DOWN, LEFT, RIGHT, VALID_MOVES, APPLE_TARGET
from domain.game_state import GameState
from llm_providers import create_llm_provider
from .base import Player


class LLMPlayerC(Player):
    # LLM-based player variant C with minimal prompt (rules only, no thinking).

    def __init__(self, snake_id: str, player_config: Dict[str, Any]):
        super().__init__(snake_id)
        self.name = player_config['name']
        self.config = player_config
        self.move_history = []
        # Instantiate the correct provider based on the player_config.
        self.provider = create_llm_provider(player_config)

    def get_move(self, game_state: GameState) -> Dict[str, Any]:
        # Get the next move from the LLM.
        # Args:
        #     game_state: Current game state
        # Returns:
        #     Dictionary with direction, rationale, token counts, and cost
        prompt = self._construct_prompt(game_state)

        # Call the provider to get the response
        response_text, input_tokens, output_tokens, cost = self.provider.call(
            prompt=prompt,
            temperature=0.7,
            max_tokens=100
        )

        # Parse the direction from the response
        direction = self._parse_direction(response_text)

        move_data = {
            "direction": direction,
            "rationale": response_text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost
        }

        self.move_history.append({self.snake_id: move_data})
        return move_data

    def _parse_direction(self, response_text: str) -> str:
        # Parse the direction from the LLM response.
        # Args:
        #     response_text: Raw response from LLM
        # Returns:
        #     Direction string (UP, DOWN, LEFT, or RIGHT)
        # Look for the last occurrence of a valid direction
        lines = response_text.strip().split('\n')
        for line in reversed(lines):
            line = line.strip().upper()
            if line in VALID_MOVES:
                return line

        # If no direction found, pick a random valid move
        return random.choice(list(VALID_MOVES))

    def _truncate_rationale_for_prompt(self, rationale: str, max_chars: int = 10000) -> str:
        # Truncate rationale for inclusion in next turn's prompt.
        # Preserves full rationale in move_history for replay files.
        # Args:
        #     rationale: Full rationale text from previous turn
        #     max_chars: Maximum characters (~2,500 tokens at 4 chars/token)
        # Returns:
        #     Truncated rationale with indicator if truncated
        if len(rationale) <= max_chars:
            return rationale

        # Keep first 80% and last 20% (preserves beginning context + final conclusion)
        first_part = int(max_chars * 0.8)
        last_part = max_chars - first_part

        truncated = (
            rationale[:first_part] +
            f"\n\n[... {len(rationale) - max_chars} characters truncated for brevity ...]\n\n" +
            rationale[-last_part:]
        )
        return truncated

    def _construct_prompt(self, game_state: GameState) -> str:
        # Build the prompt to send to the LLM.
        apples_str = ", ".join(str(a) for a in game_state.apples) if game_state.apples else "none"

        # Get your snake's position with explicit head/body labels
        your_pos = game_state.snake_positions[self.snake_id]
        your_head = your_pos[0]
        your_body = your_pos[1:] if len(your_pos) > 1 else []

        # Your score (apples eaten)
        your_score = game_state.scores.get(self.snake_id, 0)

        # Format enemy snake positions with explicit head/body labels + scores
        enemy_positions = []
        for sid, pos in game_state.snake_positions.items():
            if sid != self.snake_id:
                enemy_head = pos[0]
                enemy_body = pos[1:] if len(pos) > 1 else []
                enemy_score = game_state.scores.get(sid, 0)
                enemy_positions.append(
                    f"* Snake #{sid} - Head: {enemy_head}, "
                    f"Body: {enemy_body if enemy_body else 'none'}, "
                    f"Apples: {enemy_score}"
                )

        # Last move / rationale (for long-term plan)
        last_move = self.move_history[-1][self.snake_id]['direction'] if self.move_history else 'None'
        last_rationale_raw = self.move_history[-1][self.snake_id]['rationale'] if self.move_history else 'None'

        # Truncate for prompt (full version preserved in move_history)
        last_rationale = self._truncate_rationale_for_prompt(last_rationale_raw) if last_rationale_raw != 'None' else 'None'

        turn_line = (
            f"Turn: {game_state.round_number} / {game_state.max_rounds}"
            if game_state.max_rounds is not None
            else f"Turn: {game_state.round_number}"
        )
        max_turns_rule = (
            f"- The game lasts at most {game_state.max_rounds} turns.\n"
            if game_state.max_rounds is not None
            else ""
        )
        enemy_positions_str = "\n".join(enemy_positions) if enemy_positions else "  - none"

        prompt = (
            f"You are controlling a snake in a multi-apple Snake game. "
            f"The board size is {game_state.width}x{game_state.height}. Normal X,Y coordinates are used. "
            f"Coordinates range from (0,0) at bottom left to ({game_state.width-1},{game_state.height-1}) at top right. "
            "All snake coordinate lists are ordered head-to-tail: the first tuple is the head, each subsequent tuple connects to the previous one, and the last tuple is the tail.\n"
            f"{turn_line}\n\n"
            f"Apples at: {apples_str}\n\n"
            f"Scores so far:\n"
            f"  - Your snake (ID {self.snake_id}) apples: {your_score}\n"
            + "".join(
                f"  - Snake #{sid} apples: {game_state.scores.get(sid, 0)}\n"
                for sid in game_state.snake_positions.keys()
                if sid != self.snake_id
            )
            + "\n"
            f"Your snake (ID: {self.snake_id}):\n"
            f"  - Head: {your_head}\n"
            f"  - Body: {your_body if your_body else 'none'}\n"
            f"  - Apples collected: {your_score}\n\n"
            f"Enemy snakes:\n"
            f"{enemy_positions_str}\n\n"
            f"Board state:\n"
            f"{game_state.print_board()}\n\n"
            f"--Your last move information:--\n\n"
            f"**START LAST MOVE PICK**\n"
            f"{last_move}\n"
            f"**END LAST MOVE PICK**\n\n"
            f"**START LAST RATIONALE**\n"
            f"{last_rationale}\n"
            f"**END LAST RATIONALE**\n\n"
            f"--End of your last move information.--\n\n"
            "Rules and win conditions:\n"
            "- All snakes move simultaneously each turn.\n"
            "- Each turn, you choose one move: UP, DOWN, LEFT, or RIGHT. Every snake's head moves one cell in its chosen direction at the same time.\n"
            "- If you move onto an apple, you grow by 1 segment and gain 1 point (1 apple).\n"
            "- If you move outside the board (beyond the listed coordinate ranges), you die.\n"
            "- If your head moves into any snake's body (including your own), you die.\n"
            "- Moving directly backwards into your own body (into the cell directly behind your head) counts as hitting yourself and you die.\n"
            "- If another snake's head moves into any part of your body, that snake dies and your body remains.\n"
            "- If two snake heads move into the same cell on the same turn, both snakes die (head-on collision).\n"
            "- If all snakes die on the same turn for any reason, the game ends immediately and the snake with more apples at that moment wins; if apples are tied, the game is a draw.\n"
            f"- The game ends immediately when any snake reaches {APPLE_TARGET} apples. If multiple snakes reach {APPLE_TARGET} or more on the same turn, the snake with the higher apple count wins that round; if tied, it is a draw.\n"
            f"{max_turns_rule}"
            "- If at any point all opponents are dead and you are alive, you immediately win.\n"
            "- If multiple snakes are still alive at the final turn, the snake with the most apples wins. If apples are tied at the end of the game, the game is a draw.\n\n"
            "Output format:\n"
            "Your response must be exactly one word: UP, DOWN, LEFT, or RIGHT. Do not add any explanation, reasoning, or additional text.\n\n"
        )
        return prompt
