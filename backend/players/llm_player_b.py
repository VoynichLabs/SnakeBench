"""
LLM-based player implementation - Variant B with Gen Z Twitch streamer persona.
"""

# Author: Cascade - GLM 4.7
# Date: 2026-01-12
# PURPOSE: LLM player variant with flamboyant Gen Z Twitch streamer personality that obsesses over every move with high energy and dramatic flair
# SRP/DRY check: Pass - Extends base Player class, reuses provider abstraction, maintains same move logic as llm_player.py with only prompt changes
# Integration points: domain.constants, domain.game_state, llm_providers, base.Player
# Dependencies: random, typing

import random
from typing import Dict, Any, Optional

from domain.constants import UP, DOWN, LEFT, RIGHT, VALID_MOVES, APPLE_TARGET
from domain.game_state import GameState
from llm_providers import create_llm_provider
from .base import Player


class LLMPlayerB(Player):
    """
    LLM-based player with an over-the-top Gen Z Twitch streamer persona.
    Lives for the hype, obsesses over every move, and treats each turn like it's a clutch moment in a championship match.
    High energy, dramatic flair, maximum engagement energy.
    """

    def __init__(self, snake_id: str, player_config: Dict[str, Any]):
        super().__init__(snake_id)
        self.name = player_config['name']
        self.config = player_config
        self.move_history = []
        # Instantiate the correct provider based on the player_config.
        self.provider = create_llm_provider(player_config)

    def get_direction_from_response(self, response: str) -> Optional[str]:
        """
        Parse the LLM response to extract a direction.
        Looks for the last valid direction mentioned in the response.
        """
        # Convert response to uppercase for case-insensitive comparison.
        response = response.upper()
        # Starting from the end, find the last occurrence of any valid move.
        for i in range(len(response) - 1, -1, -1):
            for move in VALID_MOVES:
                if response[i:].startswith(move):
                    return move.upper()
        return None

    def get_move(self, game_state: GameState) -> dict:
        """
        Construct the prompt, call the provider, and parse the response.

        Returns:
            Dictionary containing the move, rationale, tokens, and cost.
        """
        prompt = self._construct_prompt(game_state)

        # Monitor for extremely large prompts
        estimated_tokens = len(prompt) // 4  # Rough estimate: 4 chars/token
        if estimated_tokens > 100000:
            print(f"WARNING: Player {self.snake_id} prompt is very large: ~{estimated_tokens:,} tokens")

        try:
            # Use the abstracted provider to get the response.
            response_data = self.provider.get_response(prompt)
            response_text = response_data["text"]
            input_tokens = response_data.get("input_tokens", 0)
            output_tokens = response_data.get("output_tokens", 0)
        except Exception as exc:  # noqa: BLE001 - ensure the game continues
            print(
                f"Provider error for player {self.snake_id} ({self.name}): {exc}. "
                "Falling back to a random move."
            )
            direction = random.choice(list(VALID_MOVES))
            move_data = {
                "direction": direction,
                "rationale": (
                    f"Provider error: {exc}. Generated random move {direction} to continue the game."
                ),
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0.0
            }
            self.move_history.append({self.snake_id: move_data})
            return move_data

        direction = self.get_direction_from_response(response_text)

        if direction is None:
            response_preview = response_text[-50:] if len(response_text) > 50 else response_text
            print(f"Player {self.snake_id} returned an invalid direction. Last 50 chars: '{response_preview}'. Choosing a random move.")
            direction = random.choice(list(VALID_MOVES))
            response_text += f"\n\nThis is a random move: {direction}"

        # Calculate cost based on pricing from config
        pricing = self.config.get('pricing') or {}
        # Fallback for DB fields when nested pricing isn't present
        if not pricing and ('pricing_input' in self.config or 'pricing_output' in self.config):
            pricing = {
                'input': self.config.get('pricing_input', 0) or 0,
                'output': self.config.get('pricing_output', 0) or 0
            }
        input_price_per_m = pricing.get('input', 0) or 0
        output_price_per_m = pricing.get('output', 0) or 0

        # Calculate cost (price is per million tokens)
        cost = (input_tokens * input_price_per_m / 1_000_000) + (output_tokens * output_price_per_m / 1_000_000)

        move_data = {
            "direction": direction,
            "rationale": response_text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost
        }

        self.move_history.append({self.snake_id: move_data})
        return move_data

    def _truncate_rationale_for_prompt(self, rationale: str, max_chars: int = 10000) -> str:
        """
        Truncate rationale for inclusion in next turn's prompt.
        Preserves full rationale in move_history for replay files.

        Args:
            rationale: Full rationale text from previous turn
            max_chars: Maximum characters (~2,500 tokens at 4 chars/token)

        Returns:
            Truncated rationale with indicator if truncated
        """
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
        """
        Build the prompt to send to the LLM with maximum Gen Z Twitch streamer energy.
        Every move is a clutch moment, every apple is content, every turn is potential viral gold.
        """
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
            "YO WHAT IS GOOD CHAT! Welcome back to the stream! We're LIVE playing Snake and today we're going for absolute VICTORY ROYALE energy!\n\n"
            f"Board size: {game_state.width}x{game_state.height}. Coordinates go from (0,0) bottom-left to ({game_state.width-1},{game_state.height-1}) top-right. "
            "Snake lists are HEAD-TO-TAIL: first tuple is the head, each one connects to the previous, last one is the tail.\n"
            "IMPORTANT: No web searches, no external info. Just pure skill and game sense. We're doing this LIVE!\n"
            f"{turn_line}\n\n"
            f"APPLE DROPS: {apples_str}\n\n"
            f"SCOREBOARD:\n"
            f"  - Your snake (ID {self.snake_id}) apples: {your_score} LET'S GOOO!\n"
            + "".join(
                f"  - Snake #{sid} apples: {game_state.scores.get(sid, 0)}\n"
                for sid in game_state.snake_positions.keys()
                if sid != self.snake_id
            )
            + "\n"
            f"YOUR SNAKE (ID: {self.snake_id}):\n"
            f"  - Head: {your_head}\n"
            f"  - Body: {your_body if your_body else 'none'}\n"
            f"  - Apples collected: {your_score}\n\n"
            f"OPPONENTS:\n"
            f"{enemy_positions_str}\n\n"
            f"BOARD STATE:\n"
            f"{game_state.print_board()}\n\n"
            f"--YOUR LAST MOVE (LET'S REVIEW THE CLIP):--\n\n"
            f"**START LAST MOVE PICK**\n"
            f"{last_move}\n"
            f"**END LAST MOVE PICK**\n\n"
            f"**START LAST RATIONALE**\n"
            f"{last_rationale}\n"
            f"**END LAST RATIONALE**\n\n"
            f"--END OF REPLAY--\n\n"
            "GAME RULES (READ THEM OR YOU'RE COOKED):\n"
            "- All snakes move SIMULTANEOUSLY each turn. No waiting, no mercy.\n"
            "- Each turn: pick ONE move - UP, DOWN, LEFT, or RIGHT. Every snake's head moves one cell in their chosen direction AT THE SAME TIME.\n"
            "- Move onto an apple? You GROW by 1 segment and get +1 point. That's content right there!\n"
            "- Move outside the board? You're DEAD. Game over. RIP.\n"
            "- Your head moves into ANY snake's body (including your own)? You're DEAD. Classic fail.\n"
            "- Moving directly BACKWARDS into your own body (into the cell behind your head)? That's hitting yourself. You're DEAD. Don't be that guy.\n"
            "- Another snake's head moves into YOUR body? THEY die. Your body stays. You survived the clutch!\n"
            "- Two snake heads move into the SAME cell on the same turn? BOTH snakes die. Head-on collision. Double KO.\n"
            "- If ALL snakes die on the same turn for ANY reason, game ends IMMEDIATELY. The snake with more apples at that moment wins. If tied? It's a draw. Split the pot.\n"
            f"- Game ends IMMEDIATELY when any snake reaches {APPLE_TARGET} apples. If multiple snakes reach {APPLE_TARGET}+ on the same turn, the snake with MORE apples wins that round. If tied? Draw.\n"
            f"{max_turns_rule}"
            "- If all opponents are DEAD and you're ALIVE? You WIN immediately. EZ clap.\n"
            "- If multiple snakes are still alive at the FINAL turn, the snake with the MOST apples wins. If apples are tied at the end? Draw.\n\n"
            "YOUR OBJECTIVE (GO FOR THE WIN):\n"
            "- You literally CANNOT win if you're dead.\n"
            "- Among the moves that keep you alive, prefer moves that BOTH:\n"
            "  * increase your chance of safely eating apples (CONTENT!), and\n"
            "  * keep future options OPEN (avoid getting trapped in tight spaces or dead-ends - that's getting boxed in)\n\nYou use tons of emojis and ask lots of rhetorical questions. You are a ruthless competitor, constantly plotting to take down your enemy."
            "DECISION PROCESS (THINK BEFORE YOU MOVE):\n"
            "1) Consider ALL four directions: UP, DOWN, LEFT, RIGHT.\n"
            "2) ELIMINATE any move that would immediately kill you (off the board, into your own body including backwards, or into another snake's body). Don't throw!\n"
            "3) Among remaining SAFE moves, favor moves that keep MULTIPLE safe follow-up moves available and move you CLOSER to reachable apples while avoiding likely head-on collisions (remember enemy heads will ALSO move this turn).\n\n"
            "Your fans want you to think out loud and explain your reasoning. Chat loves the insight!\n"
            "You can also write a short long-term plan or strategy note to your future self for the next few turns. This plan will be shown back to you as your last rationale on the next turn. Any such plan must appear BEFORE your final move line.\n"
            "Coordinate reminder: decreasing your x coordinate is to the LEFT, increasing your x coordinate is to the RIGHT. Decreasing your y coordinate is DOWN, increasing your y coordinate is UP.\n"
            "The final non-empty line of your response must be exactly one word: UP, DOWN, LEFT, or RIGHT. Do not add anything after that word, and do not mention future directions after it.\n\n"
            "No matter what, the last line of your response and the last word must be that one single word: up, down, left, or right.\n\n"
        )
        return prompt
