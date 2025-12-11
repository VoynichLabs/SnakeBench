#!/usr/bin/env python3
"""
Tests for Confidence-Weighted Placement System

Tests both the prototype implementation and the production placement_system.
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Set
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the production system for testing
from placement_system import (
    init_placement_state,
    select_next_opponent,
    update_placement_state,
    rebuild_state_from_history,
    get_confidence_for_result,
    calculate_result_confidence as calc_result_confidence_prod,
    SkillEstimate as SkillEstimateProd,
    PlacementState,
    get_final_rank,
    format_state_summary,
)

# =============================================================================
# Prototype code below (kept for comparison testing)
# =============================================================================

"""
Key insight from data analysis:
- Winners avg score: 2.6 apples
- Losers avg score: 2.3 apples
- Wall deaths (losers): avg 0.8 apples (bad loss - skill gap)
- Body collision deaths (losers): avg 4.9 apples (close game - could be fluke)
- Top models: 8-10 apples/game, 80-100% win rate
- Bottom models: 0.1-0.4 apples/game, 10-25% win rate
"""


# =============================================================================
# Confidence Scoring Based on Game Quality
# =============================================================================

@dataclass
class GameResult:
    """Detailed result of a single game."""
    opponent_id: int
    opponent_name: str
    opponent_rating: float
    opponent_rank: int
    result: str  # 'won', 'lost', 'tied'
    my_score: int
    opponent_score: int
    my_death_reason: Optional[str]  # 'wall', 'body_collision', 'head_collision', None
    my_death_round: Optional[int]
    total_rounds: int


def calculate_result_confidence(game: GameResult) -> Tuple[float, float]:
    """
    Calculate how confident we should be that this result reflects true skill.

    Returns:
        Tuple of (win_confidence, loss_confidence) where:
        - win_confidence: How much to trust a win (0.0 to 1.0)
        - loss_confidence: How much to trust a loss (0.0 to 1.0)

    Key insight: During placement, we should be MORE forgiving of losses
    than we are skeptical of wins. A fluky loss shouldn't tank placement,
    but wins should still count reasonably.
    """
    score_diff = abs(game.my_score - game.opponent_score)

    # Base confidence from score differential
    if score_diff == 0:
        base_confidence = 0.4  # Tie score - very close
    elif score_diff <= 2:
        base_confidence = 0.6  # Close game
    elif score_diff <= 5:
        base_confidence = 0.75  # Moderate gap
    elif score_diff <= 10:
        base_confidence = 0.85  # Clear gap
    else:
        base_confidence = 0.95  # Dominant performance

    win_confidence = base_confidence
    loss_confidence = base_confidence

    # Adjust loss confidence based on death reason
    if game.result == 'lost' and game.my_death_reason:
        if game.my_death_reason == 'wall':
            # Early wall death with low score = bad play, definitive loss
            if game.my_score <= 1:
                loss_confidence = min(loss_confidence + 0.15, 1.0)
            # Wall death but decent score = mistake, less definitive
            else:
                loss_confidence = loss_confidence * 0.9

        elif game.my_death_reason == 'body_collision':
            # Body collision usually happens in longer games
            # Could be tactical error, not skill gap - DISCOUNT THIS LOSS
            loss_confidence = loss_confidence * 0.5

        elif game.my_death_reason == 'head_collision':
            # Head collision = both died = essentially random
            loss_confidence = 0.25

    # Adjust for game length
    if game.total_rounds < 10:
        # Very short game - wins are less impressive, losses are more forgivable
        win_confidence *= 0.8
        loss_confidence *= 0.6
    elif game.total_rounds > 50:
        # Long game - more signal, both results more meaningful
        win_confidence = min(win_confidence * 1.1, 1.0)
        loss_confidence = min(loss_confidence * 1.1, 1.0)

    # Special case: Tie score but lost (like game 2: 3-3 but lost)
    # This is almost a tie - should barely count as a loss
    if score_diff == 0 and game.result == 'lost':
        loss_confidence *= 0.4

    return win_confidence, loss_confidence


def get_result_confidence(game: GameResult) -> float:
    """Get the appropriate confidence for this game's result."""
    win_conf, loss_conf = calculate_result_confidence(game)
    if game.result == 'won':
        return win_conf
    elif game.result == 'lost':
        return loss_conf
    else:  # tied
        return (win_conf + loss_conf) / 2


# =============================================================================
# Skill Estimate with Uncertainty (Glicko-like)
# =============================================================================

@dataclass
class SkillEstimate:
    """
    Represents our belief about a model's skill level.

    Uses a Gaussian distribution:
    - mu: Mean skill estimate (similar to ELO)
    - sigma: Uncertainty (standard deviation)

    High sigma = we're unsure about true skill
    Low sigma = we're confident in our estimate
    """
    mu: float = 1500.0  # Mean skill estimate
    sigma: float = 200.0  # Uncertainty (starts high for new models)
    games_played: int = 0
    opponents_played: Set[int] = field(default_factory=set)

    @property
    def low_bound(self) -> float:
        """Conservative estimate (2 sigma below mean)."""
        return self.mu - 2 * self.sigma

    @property
    def high_bound(self) -> float:
        """Optimistic estimate (2 sigma above mean)."""
        return self.mu + 2 * self.sigma

    def update(self, opponent_rating: float, result: str, confidence: float):
        """
        Update skill estimate based on game result.

        Uses a simplified Glicko-like update:
        - Wins against strong opponents boost mu more
        - Losses against weak opponents drop mu more
        - Confidence weights how much we trust this result
        - Sigma decreases with each game (more certainty)
        """
        # Expected score based on current estimate
        expected = 1 / (1 + 10 ** ((opponent_rating - self.mu) / 400))

        # Actual score
        if result == 'won':
            actual = 1.0
        elif result == 'lost':
            actual = 0.0
        else:  # tied
            actual = 0.5

        # K-factor scaled by uncertainty and confidence
        # Higher uncertainty = bigger updates
        # Higher confidence = bigger updates
        k = 32 * (self.sigma / 100) * confidence

        # Update mean
        self.mu += k * (actual - expected)

        # Reduce uncertainty (but not below minimum)
        # Confidence affects how much we reduce uncertainty
        min_sigma = 50  # Never go below this
        sigma_reduction = 10 * confidence
        self.sigma = max(min_sigma, self.sigma - sigma_reduction)

        self.games_played += 1


# =============================================================================
# Information Gain Opponent Selection
# =============================================================================

def calculate_information_gain(
    skill: SkillEstimate,
    opponent_rating: float,
    opponent_id: int
) -> float:
    """
    Calculate expected information gain from playing this opponent.

    High information gain when:
    - Opponent ELO is near our uncertainty range
    - We haven't played this opponent before
    - Our uncertainty is high

    Low information gain when:
    - Opponent is clearly above/below our range
    - We've played them before
    - We're already confident in our estimate
    """
    # Penalty for repeat opponent
    if opponent_id in skill.opponents_played:
        repeat_penalty = 0.5
    else:
        repeat_penalty = 1.0

    # How much would this game reduce our uncertainty?
    # Best opponents are near our current estimate
    distance_from_estimate = abs(opponent_rating - skill.mu)

    # Optimal opponent is at 1 sigma away (challenging but beatable)
    optimal_distance = skill.sigma
    distance_factor = 1.0 - min(1.0, abs(distance_from_estimate - optimal_distance) / (2 * skill.sigma))

    # Higher uncertainty = more to gain from any game
    uncertainty_factor = skill.sigma / 200  # Normalized to starting sigma

    return repeat_penalty * distance_factor * uncertainty_factor


def select_opponent_for_information_gain(
    skill: SkillEstimate,
    ranked_models: List[Tuple[int, str, float, int]],  # (id, name, elo, rank)
    top_n: int = 5
) -> Optional[Tuple[int, str, float, int]]:
    """
    Select the opponent that maximizes information gain.

    Returns the best opponent from the ranked models list.
    """
    if not ranked_models:
        return None

    # Score each potential opponent
    scored = []
    for model_id, name, elo, rank in ranked_models:
        info_gain = calculate_information_gain(skill, elo, model_id)
        scored.append((info_gain, model_id, name, elo, rank))

    # Sort by information gain (descending)
    scored.sort(reverse=True)

    # Return the best one
    if scored:
        _, model_id, name, elo, rank = scored[0]
        return (model_id, name, elo, rank)

    return None


# =============================================================================
# Confidence-Weighted Placement System
# =============================================================================

@dataclass
class ConfidencePlacementState:
    """State for confidence-weighted placement."""
    model_id: int
    skill: SkillEstimate
    max_games: int
    game_history: List[GameResult] = field(default_factory=list)


def simulate_confidence_placement(
    ranked_models: List[Tuple[int, str, float]],  # (id, name, elo)
    game_results: List[dict],  # Actual game results to replay
    max_games: int = 9
) -> Tuple[int, float, List[str]]:
    """
    Simulate confidence-weighted placement using actual game results.

    Args:
        ranked_models: Current leaderboard (id, name, elo) sorted by ELO desc
        game_results: List of actual game results to replay
        max_games: Maximum games allowed

    Returns:
        (final_rank, final_elo_estimate, game_log)
    """
    # Add rank index to models
    models_with_rank = [(m[0], m[1], m[2], idx) for idx, m in enumerate(ranked_models)]

    # Initialize skill estimate
    skill = SkillEstimate(mu=1500.0, sigma=200.0)
    game_log = []

    for i, game in enumerate(game_results[:max_games]):
        # Find opponent in our ranked list
        opponent_rank = None
        opponent_rating = game.get('opponent_rating', 1500)
        for idx, (mid, name, elo, rank) in enumerate(models_with_rank):
            if name == game.get('opponent_name') or mid == game.get('opponent_id'):
                opponent_rank = rank
                opponent_rating = elo
                break

        if opponent_rank is None:
            opponent_rank = game.get('opponent_rank', 50)

        # Create GameResult
        result = GameResult(
            opponent_id=game.get('opponent_id', 0),
            opponent_name=game.get('opponent_name', 'Unknown'),
            opponent_rating=opponent_rating,
            opponent_rank=opponent_rank,
            result=game['result'],
            my_score=game.get('my_score', 0),
            opponent_score=game.get('opponent_score', 0),
            my_death_reason=game.get('my_death_reason'),
            my_death_round=game.get('my_death_round'),
            total_rounds=game.get('total_rounds', 50)
        )

        # Calculate confidence in this result
        confidence = get_result_confidence(result)

        # Update skill estimate
        old_mu = skill.mu
        old_sigma = skill.sigma
        skill.update(opponent_rating, result.result, confidence)
        skill.opponents_played.add(result.opponent_id)

        # Log
        game_log.append(
            f"Game {i+1}: vs {result.opponent_name[:25]:<25} (#{opponent_rank}, ELO {opponent_rating:.0f}) "
            f"-> {result.result.upper():<4} | Score: {result.my_score}-{result.opponent_score} | "
            f"Conf: {confidence:.2f} | "
            f"Skill: {old_mu:.0f}±{old_sigma:.0f} -> {skill.mu:.0f}±{skill.sigma:.0f}"
        )

    # Determine final rank based on skill estimate
    final_rank = 0
    for idx, (_, _, elo, _) in enumerate(models_with_rank):
        if skill.mu < elo:
            final_rank = idx + 1

    return final_rank, skill.mu, game_log


# =============================================================================
# Compare Old vs New System
# =============================================================================

def compare_placement_systems(
    ranked_models: List[Tuple[int, str, float]],
    game_results: List[dict]
):
    """
    Compare the current binary search system vs confidence-weighted system.
    """
    print("=" * 80)
    print("PLACEMENT SYSTEM COMPARISON")
    print("=" * 80)

    N = len(ranked_models)

    # === Current Binary Search System ===
    print("\n--- CURRENT SYSTEM (Binary Search) ---")
    state_low, state_high = 0, N - 1

    for i, game in enumerate(game_results):
        target = (state_low + state_high) // 2
        result = game['result']

        # Find opponent rank
        opponent_rank = game.get('opponent_rank', target)

        if result == 'won':
            if opponent_rank == 0:
                state_low, state_high = 0, 0
            else:
                state_high = opponent_rank - 1
        elif result == 'lost':
            if opponent_rank >= N - 1:
                state_low, state_high = N - 1, N - 1
            else:
                state_low = opponent_rank + 1
        else:  # tied
            margin = 3
            state_low = max(state_low, opponent_rank - margin)
            state_high = min(state_high, opponent_rank + margin)

        state_low = max(0, state_low)
        state_high = min(N - 1, state_high)
        if state_low > state_high:
            state_low = state_high = opponent_rank

        print(f"  Game {i+1}: vs #{opponent_rank} -> {result.upper():<4} | Interval: [{state_low}, {state_high}]")

    binary_rank = state_low
    print(f"\n  FINAL RANK (Binary Search): #{binary_rank + 1}")

    # === Confidence-Weighted System ===
    print("\n--- NEW SYSTEM (Confidence-Weighted) ---")
    conf_rank, conf_elo, conf_log = simulate_confidence_placement(
        ranked_models, game_results
    )

    for line in conf_log:
        print(f"  {line}")

    print(f"\n  FINAL RANK (Confidence): #{conf_rank + 1} (ELO estimate: {conf_elo:.0f})")

    # === Summary ===
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Binary Search Rank:     #{binary_rank + 1}")
    print(f"  Confidence-Weighted:    #{conf_rank + 1}")
    print(f"  Difference:             {abs(conf_rank - binary_rank)} positions")

    if conf_rank < binary_rank:
        print(f"\n  -> Confidence system places model HIGHER (more forgiving of fluky losses)")
    elif conf_rank > binary_rank:
        print(f"\n  -> Confidence system places model LOWER (more skeptical of fluky wins)")
    else:
        print(f"\n  -> Both systems agree on placement")


# =============================================================================
# Test with actual match history from the user's example
# =============================================================================

def test_with_actual_match_history():
    """
    Test using the actual match history provided by user:

    Qwen: Qwen3 235B A22B Instruct (#58) - Tied (12-8)
    TheDrummer: Cydonia 24B V4.1 (#82) - Won (7-3)
    Qwen: Qwen2.5 VL 72B Instruct (#84) - Won (5-4)
    DeepSeek: DeepSeek V3 (#85) - Won (15-21)
    Z.AI: GLM 4.5V (#91) - Won (10-8)
    Qwen: Qwen3 Next 80B A3B Thinking (#50) - Lost (10-13) body_collision
    Qwen: Qwen3 Coder 30B A3B Instruct (#93) - Won (3-3)
    MoonshotAI: Kimi K2 Thinking (#38) - Lost (3-3) body_collision
    Qwen2.5 Coder 32B Instruct (#109) - Won (1-2)
    """
    print("\n" + "=" * 80)
    print("TEST: Actual Match History (Claude 3.7 Sonnet evaluation)")
    print("=" * 80)

    # Create mock ranked models based on the ranks mentioned
    # We'll create 150 models with ELOs spread from 1700 to 1400
    ranked_models = []
    for i in range(150):
        elo = 1700 - i * 2
        ranked_models.append((i, f"Model_{i}", elo))

    # Actual game results (chronological order - oldest first)
    game_results = [
        {
            'opponent_name': 'Qwen2.5 Coder 32B Instruct',
            'opponent_rank': 109,
            'opponent_rating': 1700 - 109 * 2,  # ~1482
            'result': 'won',
            'my_score': 1,
            'opponent_score': 2,
            'my_death_reason': None,
            'total_rounds': 20
        },
        {
            'opponent_name': 'MoonshotAI: Kimi K2 Thinking',
            'opponent_rank': 38,
            'opponent_rating': 1700 - 38 * 2,  # ~1624
            'result': 'lost',
            'my_score': 3,
            'opponent_score': 3,  # TIE SCORE but lost!
            'my_death_reason': 'body_collision',
            'total_rounds': 15
        },
        {
            'opponent_name': 'Qwen: Qwen3 Coder 30B A3B Instruct',
            'opponent_rank': 93,
            'opponent_rating': 1700 - 93 * 2,  # ~1514
            'result': 'won',
            'my_score': 3,
            'opponent_score': 3,
            'my_death_reason': None,
            'total_rounds': 20
        },
        {
            'opponent_name': 'Qwen: Qwen3 Next 80B A3B Thinking',
            'opponent_rank': 50,
            'opponent_rating': 1700 - 50 * 2,  # ~1600
            'result': 'lost',
            'my_score': 10,
            'opponent_score': 13,
            'my_death_reason': 'body_collision',
            'total_rounds': 40
        },
        {
            'opponent_name': 'Z.AI: GLM 4.5V',
            'opponent_rank': 91,
            'opponent_rating': 1700 - 91 * 2,  # ~1518
            'result': 'won',
            'my_score': 10,
            'opponent_score': 8,
            'my_death_reason': None,
            'total_rounds': 50
        },
        {
            'opponent_name': 'DeepSeek: DeepSeek V3',
            'opponent_rank': 85,
            'opponent_rating': 1700 - 85 * 2,  # ~1530
            'result': 'won',
            'my_score': 15,
            'opponent_score': 21,  # Lost on score but won the game?
            'my_death_reason': None,
            'total_rounds': 80
        },
        {
            'opponent_name': 'Qwen: Qwen2.5 VL 72B Instruct',
            'opponent_rank': 84,
            'opponent_rating': 1700 - 84 * 2,  # ~1532
            'result': 'won',
            'my_score': 5,
            'opponent_score': 4,
            'my_death_reason': None,
            'total_rounds': 30
        },
        {
            'opponent_name': 'TheDrummer: Cydonia 24B V4.1',
            'opponent_rank': 82,
            'opponent_rating': 1700 - 82 * 2,  # ~1536
            'result': 'won',
            'my_score': 7,
            'opponent_score': 3,
            'my_death_reason': None,
            'total_rounds': 35
        },
        {
            'opponent_name': 'Qwen: Qwen3 235B A22B Instruct',
            'opponent_rank': 58,
            'opponent_rating': 1700 - 58 * 2,  # ~1584
            'result': 'tied',
            'my_score': 12,
            'opponent_score': 8,
            'my_death_reason': 'head_collision',
            'total_rounds': 60
        },
    ]

    compare_placement_systems(ranked_models, game_results)

    # Show confidence scores for each game
    print("\n" + "=" * 80)
    print("CONFIDENCE SCORES FOR EACH GAME")
    print("=" * 80)

    for i, game in enumerate(game_results):
        result = GameResult(
            opponent_id=0,
            opponent_name=game['opponent_name'],
            opponent_rating=game['opponent_rating'],
            opponent_rank=game['opponent_rank'],
            result=game['result'],
            my_score=game['my_score'],
            opponent_score=game['opponent_score'],
            my_death_reason=game.get('my_death_reason'),
            my_death_round=game.get('my_death_round'),
            total_rounds=game['total_rounds']
        )

        win_conf, loss_conf = calculate_result_confidence(result)
        conf = get_result_confidence(result)
        score_diff = abs(game['my_score'] - game['opponent_score'])

        death = game.get('my_death_reason') or 'survived'
        print(f"Game {i+1}: {game['result'].upper():<4} vs #{game['opponent_rank']:<3} | "
              f"Score: {game['my_score']:>2}-{game['opponent_score']:<2} (diff:{score_diff}) | "
              f"Death: {death:<15} | "
              f"Conf: {conf:.2f} (W:{win_conf:.2f}/L:{loss_conf:.2f})")

        if game['result'] == 'lost' and loss_conf < 0.3:
            print(f"        ^ LOW CONFIDENCE LOSS ({loss_conf:.2f}) - likely a fluke, barely counts!")


def test_production_system():
    """
    Test the production placement_system with the actual match history.
    """
    print("\n" + "=" * 80)
    print("TEST: Production placement_system")
    print("=" * 80)

    # Create mock ranked models (150 models, ELOs from 1700 to 1400)
    ranked_models = []
    for i in range(150):
        elo = 1700 - i * 2
        ranked_models.append((i, f"Model_{i}", elo, i))

    # Same game history as before
    game_results = [
        {
            'opponent_id': 109,
            'opponent_name': 'Qwen2.5 Coder 32B Instruct',
            'result': 'won',
            'my_score': 1,
            'opponent_score': 2,
            'my_death_reason': None,
            'total_rounds': 20
        },
        {
            'opponent_id': 38,
            'opponent_name': 'MoonshotAI: Kimi K2 Thinking',
            'result': 'lost',
            'my_score': 3,
            'opponent_score': 3,
            'my_death_reason': 'body_collision',
            'total_rounds': 15
        },
        {
            'opponent_id': 93,
            'opponent_name': 'Qwen: Qwen3 Coder 30B A3B Instruct',
            'result': 'won',
            'my_score': 3,
            'opponent_score': 3,
            'my_death_reason': None,
            'total_rounds': 20
        },
        {
            'opponent_id': 50,
            'opponent_name': 'Qwen: Qwen3 Next 80B A3B Thinking',
            'result': 'lost',
            'my_score': 10,
            'opponent_score': 13,
            'my_death_reason': 'body_collision',
            'total_rounds': 40
        },
        {
            'opponent_id': 91,
            'opponent_name': 'Z.AI: GLM 4.5V',
            'result': 'won',
            'my_score': 10,
            'opponent_score': 8,
            'my_death_reason': None,
            'total_rounds': 50
        },
        {
            'opponent_id': 85,
            'opponent_name': 'DeepSeek: DeepSeek V3',
            'result': 'won',
            'my_score': 15,
            'opponent_score': 21,
            'my_death_reason': None,
            'total_rounds': 80
        },
        {
            'opponent_id': 84,
            'opponent_name': 'Qwen: Qwen2.5 VL 72B Instruct',
            'result': 'won',
            'my_score': 5,
            'opponent_score': 4,
            'my_death_reason': None,
            'total_rounds': 30
        },
        {
            'opponent_id': 82,
            'opponent_name': 'TheDrummer: Cydonia 24B V4.1',
            'result': 'won',
            'my_score': 7,
            'opponent_score': 3,
            'my_death_reason': None,
            'total_rounds': 35
        },
        {
            'opponent_id': 58,
            'opponent_name': 'Qwen: Qwen3 235B A22B Instruct',
            'result': 'tied',
            'my_score': 12,
            'opponent_score': 8,
            'my_death_reason': 'head_collision',
            'total_rounds': 60
        },
    ]

    # Initialize state
    state = init_placement_state(model_id=9999, max_games=9)

    print("\nProcessing games through production system:")
    print("-" * 70)

    for i, game in enumerate(game_results):
        opponent_id = game['opponent_id']
        opponent_rating = 1700 - opponent_id * 2

        # Get confidence for this result
        conf = get_confidence_for_result(
            game['result'],
            game['my_score'],
            game['opponent_score'],
            game['my_death_reason'],
            game['total_rounds']
        )

        old_mu = state.skill.mu
        old_sigma = state.skill.sigma

        # Update state
        update_placement_state(state, game, opponent_rating)

        print(f"Game {i+1}: vs {game['opponent_name'][:25]:<25} (ELO {opponent_rating})")
        print(f"  Result: {game['result'].upper():<4} | Score: {game['my_score']}-{game['opponent_score']} | Conf: {conf:.2f}")
        print(f"  Skill: {old_mu:.0f}±{old_sigma:.0f} -> {state.skill.mu:.0f}±{state.skill.sigma:.0f}")

        # Check for rematch
        if state.pending_rematch:
            print(f"  -> REMATCH REQUESTED for opponent {state.pending_rematch}")
        print()

    # Get final rank
    final_rank = get_final_rank(state, ranked_models)

    print("=" * 70)
    print("FINAL RESULTS (Production)")
    print("=" * 70)
    print(f"Skill estimate: {state.skill.mu:.0f}±{state.skill.sigma:.0f}")
    print(f"95% confidence range: [{state.skill.low_estimate:.0f}, {state.skill.high_estimate:.0f}]")
    print(f"Final rank: #{final_rank + 1}")
    print(f"Games played: {state.games_played}")


def test_information_gain_opponent_selection():
    """
    Test that information gain selects appropriate opponents.
    """
    print("\n" + "=" * 80)
    print("TEST: Information Gain Opponent Selection")
    print("=" * 80)

    # Create ranked models
    ranked_models = [(i, f"Model_{i}", 1700 - i * 10, i) for i in range(50)]

    # Initialize a fresh state
    state = init_placement_state(model_id=9999, max_games=9)

    print("\nInitial state:")
    print(f"  Skill: {state.skill.mu:.0f}±{state.skill.sigma:.0f}")

    # Select first opponent
    opponent = select_next_opponent(state, ranked_models)
    print(f"\nFirst opponent selected: {opponent[1]} (ELO {opponent[2]:.0f}, rank #{opponent[3]})")
    print("  Expected: Should be near ELO 1500 (our estimate)")

    # Simulate a win
    game = {
        'opponent_id': opponent[0],
        'result': 'won',
        'my_score': 5,
        'opponent_score': 3,
        'my_death_reason': None,
        'total_rounds': 30
    }
    update_placement_state(state, game, opponent[2])

    print(f"\nAfter winning against {opponent[1]}:")
    print(f"  Skill: {state.skill.mu:.0f}±{state.skill.sigma:.0f}")

    # Select second opponent
    opponent2 = select_next_opponent(state, ranked_models)
    print(f"\nSecond opponent selected: {opponent2[1]} (ELO {opponent2[2]:.0f}, rank #{opponent2[3]})")
    print("  Expected: Should target higher ELO now (since we won)")


def test_rematch_logic():
    """
    Test that rematch is triggered for fluky losses.
    """
    print("\n" + "=" * 80)
    print("TEST: Rematch Logic")
    print("=" * 80)

    ranked_models = [(i, f"Model_{i}", 1700 - i * 10, i) for i in range(50)]

    state = init_placement_state(model_id=9999, max_games=9)

    # Simulate a fluky loss (tie score, body collision)
    fluky_loss = {
        'opponent_id': 20,
        'result': 'lost',
        'my_score': 5,
        'opponent_score': 5,  # Tie score!
        'my_death_reason': 'body_collision',
        'total_rounds': 25
    }

    conf = get_confidence_for_result(
        fluky_loss['result'],
        fluky_loss['my_score'],
        fluky_loss['opponent_score'],
        fluky_loss['my_death_reason'],
        fluky_loss['total_rounds']
    )

    print(f"Fluky loss: Score 5-5, body_collision")
    print(f"Confidence: {conf:.2f}")

    update_placement_state(state, fluky_loss, 1500)

    if state.pending_rematch:
        print(f"REMATCH REQUESTED: opponent {state.pending_rematch}")
        print("  -> Correct! Low confidence loss triggered rematch")
    else:
        print("No rematch requested")

    # Now simulate a decisive loss
    state2 = init_placement_state(model_id=9998, max_games=9)

    decisive_loss = {
        'opponent_id': 20,
        'result': 'lost',
        'my_score': 1,
        'opponent_score': 10,
        'my_death_reason': 'wall',
        'total_rounds': 15
    }

    conf2 = get_confidence_for_result(
        decisive_loss['result'],
        decisive_loss['my_score'],
        decisive_loss['opponent_score'],
        decisive_loss['my_death_reason'],
        decisive_loss['total_rounds']
    )

    print(f"\nDecisive loss: Score 1-10, wall death")
    print(f"Confidence: {conf2:.2f}")

    update_placement_state(state2, decisive_loss, 1500)

    if state2.pending_rematch:
        print(f"REMATCH REQUESTED: opponent {state2.pending_rematch}")
    else:
        print("No rematch requested")
        print("  -> Correct! Decisive loss should not trigger rematch")


# =============================================================================
# Interval-aware placement tests (fail until interval/probe logic is implemented)
# =============================================================================


class TestIntervalAwarePlacement:
    """Tests for the interval/probe-based placement refinements."""

    def _ranked_models(self) -> List[Tuple[int, str, float, int]]:
        """
        Deterministic small leaderboard:
        rank 0: 1700, rank 1: 1600, rank 2: 1500, rank 3: 1400
        """
        return [
            (1, "Top", 1700.0, 0),
            (2, "MidHigh", 1600.0, 1),
            (3, "Mid", 1500.0, 2),
            (4, "Low", 1400.0, 3),
        ]

    def test_upward_probe_targets_upper_interval(self):
        """
        After one game (odd index), selection should probe high in the interval,
        preferring the upper quartile rather than hovering near current mu,
        even when sigma is small.
        """
        state = init_placement_state(model_id=999, max_games=9)
        state.games_played = 1  # Next pick should be an upward probe
        # Seed an interval that spans the board; mu sits near the middle
        state.skill.mu = 1500.0
        state.skill.sigma = 50.0  # Tight sigma would normally keep us near mu
        state.rating_low = 1650.0
        state.rating_high = 1750.0

        ranked_models = self._ranked_models()
        opponent = select_next_opponent(state, ranked_models=ranked_models)

        # Expect it to honor the interval probe and pick the top candidate (1700)
        assert opponent is not None
        assert opponent[0] == 1  # Top

    def test_draw_vs_low_does_not_cap_ceiling(self):
        """
        A draw against a much lower-rated opponent should not collapse the upper bound,
        to avoid getting stuck with weak opponents early.
        """
        state = init_placement_state(model_id=999, max_games=9)
        state.rating_low = 1200.0
        state.rating_high = 1800.0
        state.skill.mu = 1500.0
        state.skill.sigma = 200.0

        game_result = {
            "opponent_id": 123,
            "result": "tied",
            "my_score": 4,
            "opponent_score": 4,
            "my_death_reason": None,
            "total_rounds": 30,
        }

        update_placement_state(state, game_result, opponent_rating=1300.0)

        # Upper bound should remain high, and floor should rise from its initial value
        assert state.rating_high >= 1700.0
        assert state.rating_low > 1200.0


if __name__ == "__main__":
    test_with_actual_match_history()
    test_production_system()
    test_information_gain_opponent_selection()
    test_rematch_logic()
