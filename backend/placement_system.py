"""
Confidence-Weighted Placement System

An improved placement system that:
1. Uses a skill estimate with uncertainty (Glicko-like) instead of hard binary bounds
2. Weights game results by how decisive they were (score differential, death type)
3. Selects opponents to maximize information gain
4. Allows rematches for inconclusive results
5. Is more forgiving of fluky losses during placement

Key insight from data analysis:
- Wall deaths with low score = definitive skill gap
- Body collisions with close scores = tactical error, could be fluke
- Head collisions = essentially random
- Top models: 8-10 apples/game, bottom models: 0.1-0.4 apples/game
"""

from typing import Optional, Tuple, Set, List, Dict, Any
from dataclasses import dataclass, field
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database_postgres import get_connection


# =============================================================================
# Configuration
# =============================================================================

# Initial uncertainty for new models (higher = less confident in initial estimate)
INITIAL_SIGMA = 200.0

# Minimum uncertainty (never go below this even after many games)
MIN_SIGMA = 50.0

# Sigma reduction per game (scaled by confidence)
SIGMA_REDUCTION_PER_GAME = 15.0

# Base K-factor for skill updates
BASE_K = 32.0

# Threshold below which a loss is considered "fluky" and may warrant rematch
FLUKY_LOSS_THRESHOLD = 0.25

# Maximum rematches allowed per opponent
MAX_REMATCHES = 1


# =============================================================================
# Game Result and Confidence Scoring
# =============================================================================

@dataclass
class GameResultDetail:
    """Detailed result of a single evaluation game."""
    game_id: str
    opponent_id: int
    opponent_name: str
    opponent_elo: float
    opponent_rank: int
    result: str  # 'won', 'lost', 'tied'
    my_score: int
    opponent_score: int
    my_death_reason: Optional[str]  # 'wall', 'body_collision', 'head_collision', None
    my_death_round: Optional[int]
    total_rounds: int


def calculate_result_confidence(
    result: str,
    my_score: int,
    opponent_score: int,
    my_death_reason: Optional[str],
    total_rounds: int
) -> Tuple[float, float]:
    """
    Calculate confidence scores for win and loss interpretations.

    Returns:
        Tuple of (win_confidence, loss_confidence)
        - win_confidence: How much to trust this if it's a win (0.0 to 1.0)
        - loss_confidence: How much to trust this if it's a loss (0.0 to 1.0)

    Key principle: During placement, be MORE forgiving of losses than
    skeptical of wins. A fluky loss shouldn't tank placement.
    """
    score_diff = abs(my_score - opponent_score)

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
    if result == 'lost' and my_death_reason:
        if my_death_reason == 'wall':
            # Wall death interpretation depends on score
            if my_score <= 1:
                # Early wall death with low score = bad play, definitive loss
                loss_confidence = min(loss_confidence + 0.15, 1.0)
            else:
                # Wall death but decent score = mistake under pressure
                loss_confidence = loss_confidence * 0.9

        elif my_death_reason == 'body_collision':
            # Body collision usually happens in longer, competitive games
            # Could be tactical error, not skill gap - DISCOUNT THIS LOSS
            loss_confidence = loss_confidence * 0.5

        elif my_death_reason == 'head_collision':
            # Head collision = both died = essentially random
            loss_confidence = 0.25

    # Adjust for game length
    if total_rounds < 10:
        # Very short game - wins less impressive, losses more forgivable
        win_confidence *= 0.8
        loss_confidence *= 0.6
    elif total_rounds > 50:
        # Long game - more signal, both results more meaningful
        win_confidence = min(win_confidence * 1.1, 1.0)
        loss_confidence = min(loss_confidence * 1.1, 1.0)

    # Special case: Tie score but one player lost (e.g., 3-3 but died)
    # This is almost a tie - should barely count as a loss
    if score_diff == 0 and result == 'lost':
        loss_confidence *= 0.4

    return win_confidence, loss_confidence


def get_confidence_for_result(
    result: str,
    my_score: int,
    opponent_score: int,
    my_death_reason: Optional[str],
    total_rounds: int
) -> float:
    """Get the appropriate confidence for the actual game result."""
    win_conf, loss_conf = calculate_result_confidence(
        result, my_score, opponent_score, my_death_reason, total_rounds
    )

    if result == 'won':
        return win_conf
    elif result == 'lost':
        return loss_conf
    else:  # tied
        return (win_conf + loss_conf) / 2


# =============================================================================
# Skill Estimate (Glicko-like)
# =============================================================================

@dataclass
class SkillEstimate:
    """
    Represents our belief about a model's skill level.

    Uses a Gaussian-like distribution:
    - mu: Mean skill estimate (similar to ELO, starts at 1500)
    - sigma: Uncertainty/standard deviation (starts high, decreases with games)
    """
    mu: float = 1500.0
    sigma: float = INITIAL_SIGMA

    @property
    def low_estimate(self) -> float:
        """Conservative estimate (2 sigma below mean)."""
        return self.mu - 2 * self.sigma

    @property
    def high_estimate(self) -> float:
        """Optimistic estimate (2 sigma above mean)."""
        return self.mu + 2 * self.sigma

    def update(self, opponent_elo: float, result: str, confidence: float) -> None:
        """
        Update skill estimate based on game result.

        Args:
            opponent_elo: ELO rating of the opponent
            result: 'won', 'lost', or 'tied'
            confidence: How much to trust this result (0.0 to 1.0)
        """
        # Expected score based on current estimate
        expected = 1 / (1 + 10 ** ((opponent_elo - self.mu) / 400))

        # Actual score
        if result == 'won':
            actual = 1.0
        elif result == 'lost':
            actual = 0.0
        else:  # tied
            actual = 0.5

        # K-factor scaled by uncertainty and confidence
        # Higher uncertainty = bigger updates (we're less sure, so new info matters more)
        # Higher confidence = bigger updates (we trust this result more)
        k = BASE_K * (self.sigma / 100) * confidence

        # Update mean skill estimate
        self.mu += k * (actual - expected)

        # Reduce uncertainty (but not below minimum)
        # Confidence affects how much we reduce uncertainty
        sigma_reduction = SIGMA_REDUCTION_PER_GAME * confidence
        self.sigma = max(MIN_SIGMA, self.sigma - sigma_reduction)

    def to_dict(self) -> Dict[str, float]:
        """Serialize to dictionary."""
        return {'mu': self.mu, 'sigma': self.sigma}

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'SkillEstimate':
        """Deserialize from dictionary."""
        return cls(mu=data.get('mu', 1500.0), sigma=data.get('sigma', INITIAL_SIGMA))


# =============================================================================
# Placement State
# =============================================================================

@dataclass
class PlacementState:
    """
    State tracking for confidence-weighted placement.

    Uses probabilistic skill estimate instead of hard binary bounds.
    """
    model_id: int
    skill: SkillEstimate
    games_played: int
    max_games: int
    opponents_played: Set[int]  # opponent_id -> times played
    opponent_play_counts: Dict[int, int]  # Track how many times each opponent played
    game_history: List[Dict[str, Any]]  # Detailed history for reconstruction
    pending_rematch: Optional[int] = None  # opponent_id if rematch is pending

    def __post_init__(self):
        if self.opponent_play_counts is None:
            self.opponent_play_counts = {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'model_id': self.model_id,
            'skill': self.skill.to_dict(),
            'games_played': self.games_played,
            'max_games': self.max_games,
            'opponents_played': list(self.opponents_played),
            'opponent_play_counts': self.opponent_play_counts,
            'game_history': self.game_history,
            'pending_rematch': self.pending_rematch,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlacementState':
        """Deserialize from dictionary."""
        return cls(
            model_id=data['model_id'],
            skill=SkillEstimate.from_dict(data.get('skill', {})),
            games_played=data.get('games_played', 0),
            max_games=data.get('max_games', 9),
            opponents_played=set(data.get('opponents_played', [])),
            opponent_play_counts=data.get('opponent_play_counts', {}),
            game_history=data.get('game_history', []),
            pending_rematch=data.get('pending_rematch'),
        )


# =============================================================================
# Core Functions
# =============================================================================

def get_ranked_models_by_index() -> List[Tuple[int, str, float, int]]:
    """
    Get all ranked models sorted by ELO (best to worst).

    Returns:
        List of tuples (model_id, name, elo_rating, rank_index)
        where rank_index 0 = best, N-1 = worst
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, name, elo_rating
            FROM models
            WHERE test_status = 'ranked' AND is_active = TRUE
            ORDER BY elo_rating DESC
        """)

        models = cursor.fetchall()
        return [(m['id'], m['name'], m['elo_rating'], idx)
                for idx, m in enumerate(models)]

    finally:
        conn.close()


def init_placement_state(model_id: int, max_games: int = 9) -> PlacementState:
    """
    Initialize placement state for a new model.

    Args:
        model_id: ID of the model to place
        max_games: Maximum games to play (default: 9)

    Returns:
        Initialized PlacementState
    """
    return PlacementState(
        model_id=model_id,
        skill=SkillEstimate(mu=1500.0, sigma=INITIAL_SIGMA),
        games_played=0,
        max_games=max_games,
        opponents_played=set(),
        opponent_play_counts={},
        game_history=[],
        pending_rematch=None,
    )


def calculate_information_gain(
    skill: SkillEstimate,
    opponent_elo: float,
    opponent_id: int,
    play_count: int
) -> float:
    """
    Calculate expected information gain from playing this opponent.

    High information gain when:
    - Opponent ELO is within our uncertainty range
    - We haven't played this opponent much
    - Our uncertainty is still high

    Args:
        skill: Current skill estimate
        opponent_elo: ELO of potential opponent
        opponent_id: ID of potential opponent
        play_count: How many times we've played this opponent

    Returns:
        Information gain score (higher = more informative)
    """
    # Penalty for playing same opponent multiple times
    repeat_penalty = 1.0 / (1 + play_count)

    # How informative is this opponent given our current uncertainty?
    # Best opponents are near our current estimate (challenging but beatable)
    distance_from_estimate = abs(opponent_elo - skill.mu)

    # Optimal opponent is about 1 sigma away
    # (not too easy, not too hard)
    optimal_distance = skill.sigma * 0.75

    # Score based on distance from optimal
    if skill.sigma > 0:
        distance_factor = math.exp(-((distance_from_estimate - optimal_distance) ** 2) / (2 * skill.sigma ** 2))
    else:
        distance_factor = 1.0 if distance_from_estimate < 50 else 0.0

    # Higher uncertainty = more to gain from any game
    uncertainty_factor = skill.sigma / INITIAL_SIGMA

    # Combine factors
    return repeat_penalty * distance_factor * (0.5 + 0.5 * uncertainty_factor)


def should_rematch(
    result: str,
    confidence: float,
    opponent_id: int,
    play_count: int
) -> bool:
    """
    Determine if we should rematch this opponent.

    Rematch if:
    - Lost with very low confidence (fluky loss)
    - Haven't exceeded max rematches for this opponent

    Args:
        result: Game result ('won', 'lost', 'tied')
        confidence: Confidence in the result
        opponent_id: ID of the opponent
        play_count: Times played this opponent

    Returns:
        True if rematch is warranted
    """
    if result != 'lost':
        return False

    if play_count >= MAX_REMATCHES + 1:  # +1 because we already played once
        return False

    return confidence < FLUKY_LOSS_THRESHOLD


def select_next_opponent(
    state: PlacementState,
    ranked_models: Optional[List[Tuple[int, str, float, int]]] = None
) -> Optional[Tuple[int, str, float, int]]:
    """
    Select the next opponent using information gain strategy.

    Strategy:
    1. If there's a pending rematch, do that first
    2. Otherwise, pick opponent that maximizes information gain
    3. Prefer opponents we haven't played
    4. Target opponents near our skill estimate

    Args:
        state: Current placement state
        ranked_models: Optional pre-fetched ranked models list

    Returns:
        Tuple of (opponent_id, opponent_name, opponent_elo, opponent_rank) or None
    """
    if state.games_played >= state.max_games:
        return None

    if ranked_models is None:
        ranked_models = get_ranked_models_by_index()

    if not ranked_models:
        print("  No ranked models available for placement")
        return None

    # Filter out the model being tested
    candidates = [m for m in ranked_models if m[0] != state.model_id]

    if not candidates:
        return None

    # Check for pending rematch
    if state.pending_rematch is not None:
        for model_id, name, elo, rank in candidates:
            if model_id == state.pending_rematch:
                return (model_id, name, elo, rank)
        # Rematch opponent not found (maybe deactivated), clear it
        state.pending_rematch = None

    # Score each candidate by information gain
    scored_candidates = []
    for model_id, name, elo, rank in candidates:
        play_count = state.opponent_play_counts.get(model_id, 0)
        info_gain = calculate_information_gain(state.skill, elo, model_id, play_count)
        scored_candidates.append((info_gain, model_id, name, elo, rank))

    # Sort by information gain (descending)
    scored_candidates.sort(reverse=True, key=lambda x: x[0])

    # Return the best candidate
    if scored_candidates:
        _, model_id, name, elo, rank = scored_candidates[0]
        return (model_id, name, elo, rank)

    return None


def update_placement_state(
    state: PlacementState,
    game_result: Dict[str, Any],
    opponent_elo: float
) -> None:
    """
    Update placement state based on a completed game.

    Args:
        state: Placement state to update (modified in place)
        game_result: Dictionary with game details:
            - opponent_id: int
            - result: 'won', 'lost', 'tied'
            - my_score: int
            - opponent_score: int
            - my_death_reason: Optional[str]
            - total_rounds: int
        opponent_elo: ELO of the opponent at match time
    """
    opponent_id = game_result['opponent_id']
    result = game_result['result']
    my_score = game_result.get('my_score', 0)
    opponent_score = game_result.get('opponent_score', 0)
    my_death_reason = game_result.get('my_death_reason')
    total_rounds = game_result.get('total_rounds', 50)

    # Calculate confidence in this result
    confidence = get_confidence_for_result(
        result, my_score, opponent_score, my_death_reason, total_rounds
    )

    # Update skill estimate
    state.skill.update(opponent_elo, result, confidence)

    # Track opponent
    state.opponents_played.add(opponent_id)
    state.opponent_play_counts[opponent_id] = state.opponent_play_counts.get(opponent_id, 0) + 1

    # Add to history
    state.game_history.append({
        **game_result,
        'opponent_elo': opponent_elo,
        'confidence': confidence,
    })

    # Increment games played
    state.games_played += 1

    # Clear any pending rematch (we just played it)
    if state.pending_rematch == opponent_id:
        state.pending_rematch = None

    # Check if we should request a rematch
    play_count = state.opponent_play_counts[opponent_id]
    if should_rematch(result, confidence, opponent_id, play_count):
        state.pending_rematch = opponent_id
        print(f"  Low confidence loss ({confidence:.2f}) - scheduling rematch")


def get_final_rank(
    state: PlacementState,
    ranked_models: Optional[List[Tuple[int, str, float, int]]] = None
) -> int:
    """
    Determine final rank based on skill estimate.

    Compares the model's estimated skill (mu) against the ELO ratings
    of all ranked models to find where it belongs.

    Args:
        state: Final placement state
        ranked_models: Optional pre-fetched ranked models

    Returns:
        Final rank index (0 = best)
    """
    if ranked_models is None:
        ranked_models = get_ranked_models_by_index()

    if not ranked_models:
        return 0

    # Find where our skill estimate fits in the leaderboard
    final_rank = 0
    for idx, (_, _, elo, _) in enumerate(ranked_models):
        if state.skill.mu < elo:
            final_rank = idx + 1

    return final_rank


def rebuild_state_from_history(
    model_id: int,
    max_games: int,
    history: List[Dict[str, Any]],
    ranked_models: List[Tuple[int, str, float, int]]
) -> Tuple[PlacementState, int]:
    """
    Reconstruct placement state from completed evaluation games.

    This is called when resuming evaluation for a model that has
    already played some games.

    Args:
        model_id: ID of the model being evaluated
        max_games: Maximum games for this evaluation
        history: List of completed game records from database
        ranked_models: Current ranked models list

    Returns:
        Tuple of (reconstructed state, number of completed games)
    """
    # Create a lookup for opponent ELOs
    elo_lookup = {m[0]: m[2] for m in ranked_models}

    # Initialize fresh state
    state = init_placement_state(model_id, max_games)

    for record in history:
        opponent_id = record.get('opponent_id')
        result = record.get('model_result') or record.get('result')

        if opponent_id is None or result is None:
            continue

        # Get opponent ELO (use stored value or look up current)
        opponent_elo = record.get('opponent_elo')
        if opponent_elo is None:
            opponent_elo = elo_lookup.get(opponent_id, 1500.0)

        # Build game result dict
        game_result = {
            'opponent_id': opponent_id,
            'result': result,
            'my_score': record.get('my_score', 0),
            'opponent_score': record.get('opponent_score', 0),
            'my_death_reason': record.get('my_death_reason'),
            'total_rounds': record.get('total_rounds', 50),
        }

        # Update state with this game
        update_placement_state(state, game_result, opponent_elo)

    return state, len(history)


# =============================================================================
# Utility Functions
# =============================================================================

def get_opponent_rank_index(
    opponent_id: int,
    ranked_models: Optional[List[Tuple[int, str, float, int]]] = None
) -> Optional[int]:
    """
    Get the current rank index of an opponent.

    Args:
        opponent_id: ID of the opponent model
        ranked_models: Optional pre-fetched ranked models

    Returns:
        Rank index (0 = best) or None if not found
    """
    if ranked_models is None:
        ranked_models = get_ranked_models_by_index()

    for model_id, _, _, rank_index in ranked_models:
        if model_id == opponent_id:
            return rank_index

    return None


def format_state_summary(state: PlacementState) -> str:
    """Format a human-readable summary of placement state."""
    return (
        f"Skill: {state.skill.mu:.0f}±{state.skill.sigma:.0f} | "
        f"Games: {state.games_played}/{state.max_games} | "
        f"Range: [{state.skill.low_estimate:.0f}, {state.skill.high_estimate:.0f}]"
    )
