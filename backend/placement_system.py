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
from services.trueskill_engine import (
    DEFAULT_MU as TS_DEFAULT_MU,
    DEFAULT_SIGMA as TS_DEFAULT_SIGMA,
    DEFAULT_BETA as TS_DEFAULT_BETA,
)


# =============================================================================
# Configuration
# =============================================================================

# Initial uncertainty for new models (TrueSkill sigma)
INITIAL_SIGMA = TS_DEFAULT_SIGMA

# Minimum uncertainty (never go below this even after many games)
MIN_SIGMA = 2.0

# Sigma reduction per game (scaled by confidence)
SIGMA_REDUCTION_PER_GAME = 0.8

# Base K-factor for skill updates (scaled for TrueSkill units)
BASE_K = 3.0

# Threshold below which a loss is considered "fluky" and may warrant rematch
FLUKY_LOSS_THRESHOLD = 0.25

# Maximum rematches allowed per opponent
MAX_REMATCHES = 1

# Require a high-confidence win before doing an upward probe
HIGH_CONF_WIN_PROBE_THRESHOLD = 0.6
# Length of consecutive high-confidence wins to trigger a more aggressive probe
AGGRESSIVE_PROBE_WIN_STREAK = 3
# Target fraction of interval when aggressive probe kicks in
AGGRESSIVE_PROBE_TARGET_FRACTION = 0.8
# Maximum allowed upward jump in opponent rating (conservative TrueSkill) per pick
MAX_RATING_JUMP = 20.0
# Minimum rating delta upward after a win (avoid replaying same/lower while on a climb)
MIN_ASCEND_RATING_DELTA = 0.01

# Interval/search configuration (TrueSkill exposed scale is roughly -20..40)
INTERVAL_BUFFER = 5.0
DEFAULT_RATING_LOW = -20.0
DEFAULT_RATING_HIGH = 40.0
TYPICAL_MAX_MARGIN = 15.0  # Used to normalize score differentials


def clamp(value: float, min_value: float, max_value: float) -> float:
    """Clamp a numeric value into [min_value, max_value]."""
    return max(min_value, min(max_value, value))


def normalize_margin(raw_margin: float) -> float:
    """Map a raw score differential into [0, 1] for multiplier calculations."""
    if TYPICAL_MAX_MARGIN <= 0:
        return 0.0
    return clamp(raw_margin / TYPICAL_MAX_MARGIN, 0.0, 1.0)

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
    - mu: Mean skill estimate (TrueSkill scale, starts at TS_DEFAULT_MU)
    - sigma: Uncertainty/standard deviation (starts high, decreases with games)
    """
    mu: float = TS_DEFAULT_MU
    sigma: float = INITIAL_SIGMA

    @property
    def low_estimate(self) -> float:
        """Conservative estimate (2 sigma below mean)."""
        return self.mu - 2 * self.sigma

    @property
    def high_estimate(self) -> float:
        """Optimistic estimate (2 sigma above mean)."""
        return self.mu + 2 * self.sigma

    def update(
        self,
        opponent_elo: float,
        result: str,
        confidence: float,
        margin_factor: float = 1.0,
        norm_margin: float = 0.0,
    ) -> None:
        """
        Update skill estimate based on game result.

        Args:
            opponent_elo: ELO rating of the opponent
            result: 'won', 'lost', or 'tied'
            confidence: How much to trust this result (0.0 to 1.0)
            margin_factor: Multiplier based on score differential and surprise
            norm_margin: Normalized margin (0..1) used for sigma reduction
        """
        # Expected score based on current estimate using TrueSkill beta as scale.
        scale = math.sqrt(2) * TS_DEFAULT_BETA
        expected = 1 / (1 + math.exp(-(self.mu - opponent_elo) / scale))

        # Actual score
        if result == 'won':
            actual = 1.0
        elif result == 'lost':
            actual = 0.0
        else:  # tied
            actual = 0.5

        # K-factor scaled by uncertainty and confidence
        k = BASE_K * (self.sigma / TS_DEFAULT_SIGMA) * confidence

        # Update mean skill estimate
        delta = k * margin_factor * (actual - expected)
        # Cap extreme jumps to avoid volatility on noisy results
        delta = clamp(delta, -1.2 * k, 1.2 * k)
        self.mu += delta

        # Reduce uncertainty (but not below minimum)
        # Confidence affects how much we reduce uncertainty
        sigma_reduction = SIGMA_REDUCTION_PER_GAME * confidence * (0.5 + 0.5 * norm_margin)
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
    elo_low: float = DEFAULT_RATING_LOW  # Lower bound of current search interval
    elo_high: float = DEFAULT_RATING_HIGH  # Upper bound of current search interval

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
            'elo_low': self.elo_low,
            'elo_high': self.elo_high,
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
            elo_low=data.get('elo_low', DEFAULT_RATING_LOW),
            elo_high=data.get('elo_high', DEFAULT_RATING_HIGH),
        )


# =============================================================================
# Core Functions
# =============================================================================

def get_ranked_models_by_index() -> List[Tuple[int, str, float, int]]:
    """
    Get all ranked models sorted by conservative TrueSkill (exposed).

    Returns:
        List of tuples (model_id, name, rating_exposed, rank_index)
        where rank_index 0 = best, N-1 = worst
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, name, trueskill_exposed
            FROM models
            WHERE test_status = 'ranked' AND is_active = TRUE
            ORDER BY trueskill_exposed DESC NULLS LAST
        """)

        models = cursor.fetchall()
        return [(m['id'], m['name'], m.get('trueskill_exposed') or 0.0, idx)
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
        skill=SkillEstimate(mu=TS_DEFAULT_MU, sigma=INITIAL_SIGMA),
        games_played=0,
        max_games=max_games,
        opponents_played=set(),
        opponent_play_counts={},
        game_history=[],
        pending_rematch=None,
        elo_low=DEFAULT_RATING_LOW,
        elo_high=DEFAULT_RATING_HIGH,
    )


def calculate_information_gain(
    skill: SkillEstimate,
    opponent_rating: float,
    opponent_id: int,
    play_count: int
) -> float:
    """
    Calculate expected information gain from playing this opponent.

    High information gain when:
    - Opponent rating is within our uncertainty range
    - We haven't played this opponent much
    - Our uncertainty is still high

    Args:
        skill: Current skill estimate
        opponent_rating: rating of potential opponent (trueskill_exposed)
        opponent_id: ID of potential opponent
        play_count: How many times we've played this opponent

    Returns:
        Information gain score (higher = more informative)
    """
    # Penalty for playing same opponent multiple times
    repeat_penalty = 1.0 / (1 + play_count)

    # How informative is this opponent given our current uncertainty?
    # Best opponents are near our current estimate (challenging but beatable)
    distance_from_estimate = abs(opponent_rating - skill.mu)

    # Optimal opponent is about 0.5 sigma away
    # (not too easy, not too hard)
    optimal_distance = skill.sigma * 0.5

    # Score based on distance from optimal
    if skill.sigma > 0:
        distance_factor = math.exp(-((distance_from_estimate - optimal_distance) ** 2) / (2 * skill.sigma ** 2))
    else:
        distance_factor = 1.0 if distance_from_estimate < 50 else 0.0

    # Higher uncertainty = more to gain from any game
    uncertainty_factor = skill.sigma / INITIAL_SIGMA

    # Combine factors
    return repeat_penalty * distance_factor * (0.5 + 0.5 * uncertainty_factor)


def ensure_interval_bounds(
    state: PlacementState,
    ranked_models: Optional[List[Tuple[int, str, float, int]]] = None
) -> Tuple[float, float]:
    """
    Ensure the placement state has rating interval bounds seeded.

    If missing, derive from the leaderboard with a small buffer; otherwise
    fall back to sensible defaults.
    """
    if getattr(state, "elo_low", None) is None or getattr(state, "elo_high", None) is None:
        if ranked_models:
            ratings = [m[2] for m in ranked_models]
            state.elo_low = min(ratings) - INTERVAL_BUFFER
            state.elo_high = max(ratings) + INTERVAL_BUFFER
        else:
            state.elo_low = DEFAULT_RATING_LOW
            state.elo_high = DEFAULT_RATING_HIGH
    return state.elo_low, state.elo_high


def window_from_sigma(sigma: float, norm_margin: float) -> float:
    """
    Convert uncertainty + margin into a tightening window for the interval.

    Higher sigma -> wider steps; bigger margins widen slightly.
    """
    base = sigma * 1.5 + 2.0
    base = clamp(base, 4.0, 20.0)
    return base + norm_margin * 2.0


def tighten_interval(
    state: PlacementState,
    opponent_rating: float,
    result: str,
    norm_margin: float,
    expected: float,
) -> None:
    """
    Update the [elo_low, elo_high] interval based on the result.

    Wins lift the floor, losses lower the ceiling, draws only raise the floor
    when the opponent is well below current belief.
    """
    step = window_from_sigma(state.skill.sigma, norm_margin)

    if result == 'won':
        state.elo_low = max(state.elo_low, opponent_rating - step)
    elif result == 'lost':
        state.elo_high = min(state.elo_high, opponent_rating + step)
    else:  # tied
        # Only lift the floor on draws vs clearly weaker opponents
        if opponent_rating < state.skill.mu - 0.5 * state.skill.sigma:
            state.elo_low = max(state.elo_low, opponent_rating - step / 2)

    # Guard against inverted bounds
    if state.elo_low > state.elo_high:
        mid = (state.elo_low + state.elo_high) / 2
        state.elo_low = mid
        state.elo_high = mid


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
    opponent, _ = select_next_opponent_with_reason(state, ranked_models=ranked_models)
    return opponent


def select_next_opponent_with_reason(
    state: PlacementState,
    ranked_models: Optional[List[Tuple[int, str, float, int]]] = None
) -> Tuple[Optional[Tuple[int, str, float, int]], Dict[str, Any]]:
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
        (opponent tuple, debug dict)
        opponent tuple: (opponent_id, opponent_name, opponent_rating, opponent_rank) or None
        debug dict: selection metadata for logging
    """
    debug: Dict[str, Any] = {}

    if state.games_played >= state.max_games:
        return None, debug

    if ranked_models is None:
        ranked_models = get_ranked_models_by_index()

    if not ranked_models:
        print("  No ranked models available for placement")
        return None, debug

    # Filter out the model being tested
    candidates = [m for m in ranked_models if m[0] != state.model_id]

    if not candidates:
        return None, debug

    # Ensure interval bounds are seeded
    elo_low, elo_high = ensure_interval_bounds(state, ranked_models)
    debug["interval"] = (elo_low, elo_high)

    # Check for pending rematch
    if state.pending_rematch is not None:
        for model_id, name, elo, rank in candidates:
            if model_id == state.pending_rematch:
                debug.update({
                    "reason": "pending_rematch",
                    "opponent_id": model_id,
                })
                return (model_id, name, elo, rank), debug
        # Rematch opponent not found (maybe deactivated), clear it
        state.pending_rematch = None

    # If we just won, prefer strictly higher-rated opponents to keep climbing.
    last_game = state.game_history[-1] if state.game_history else None
    last_win_elo = None
    if last_game and last_game.get("result") == "won":
        last_win_elo = last_game.get("opponent_elo")

    filtered_candidates = candidates
    if last_win_elo is not None:
        upward = [c for c in candidates if c[2] > last_win_elo + MIN_ASCEND_RATING_DELTA]
        if upward:
            filtered_candidates = upward
            debug["ascend_filter_from"] = last_win_elo
            debug["ascend_filter_count"] = len(upward)

    candidates = filtered_candidates

    # Choose a target rating: midpoint by default; escalate on confidence streaks.
    interval_span = max(0.0, elo_high - elo_low)
    target_fraction = 0.5
    probe_reason = "midpoint"

    # Compute confident win streak (most recent backwards)
    streak = 0
    for g in reversed(state.game_history):
        if g.get("result") == "won" and g.get("confidence", 0) >= HIGH_CONF_WIN_PROBE_THRESHOLD:
            streak += 1
        else:
            break

    last_game = state.game_history[-1] if state.game_history else None
    last_confidence = None
    if last_game and last_game.get("result") == "won":
        last_confidence = last_game.get("confidence")

    if streak >= AGGRESSIVE_PROBE_WIN_STREAK:
        target_fraction = AGGRESSIVE_PROBE_TARGET_FRACTION
        probe_reason = "upward_probe_streak"
    else:
        if state.games_played % 2 == 1:
            if last_confidence is not None and last_confidence >= HIGH_CONF_WIN_PROBE_THRESHOLD:
                target_fraction = 0.6
                probe_reason = "upward_probe"
            else:
                probe_reason = "midpoint_hold"

    target_elo = elo_low + target_fraction * interval_span

    # Cap how far above the last opponent we can jump in one pick to avoid
    # skipping large swaths of the ladder in a single move.
    if state.game_history:
        last_opponent_rating = state.game_history[-1].get("opponent_elo")
        if last_opponent_rating is not None:
            target_elo = min(target_elo, last_opponent_rating + MAX_RATING_JUMP)

    debug["target_elo"] = target_elo
    debug["probe"] = probe_reason

    # Score each candidate by distance to target, breaking ties with information gain
    best = None
    best_key = None
    for model_id, name, elo, rank in candidates:
        play_count = state.opponent_play_counts.get(model_id, 0)
        info_gain = calculate_information_gain(state.skill, elo, model_id, play_count)
        distance = abs(elo - target_elo)
        # Prefer closer to target; if equal distance, pick higher info_gain
        key = (distance, -info_gain)
        if best is None or key < best_key:
            best = (model_id, name, elo, rank)
            best_key = key
            debug.update({
                "selected_id": model_id,
                "selected_name": name,
                "selected_elo": elo,
                "selected_rank": rank,
                "distance_to_target": distance,
                "info_gain": info_gain,
                "play_count": play_count,
            })

    return best, debug


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
    opponent_elo: rating of the opponent at match time (trueskill_exposed)
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

    # Ensure interval bounds exist before updates
    ensure_interval_bounds(state)

    # Expected vs actual for rating update
    scale = math.sqrt(2) * TS_DEFAULT_BETA
    expected = 1 / (1 + math.exp(-(state.skill.mu - opponent_elo) / scale))
    if result == 'won':
        actual = 1.0
    elif result == 'lost':
        actual = 0.0
    else:
        actual = 0.5

    # Margin-aware multiplier
    norm_margin = normalize_margin(abs(my_score - opponent_score))
    surprise = actual - expected
    margin_factor = 1 + surprise * norm_margin
    margin_factor = clamp(margin_factor, 0.5, 1.5)

    # Update skill estimate
    state.skill.update(
        opponent_elo,
        result,
        confidence,
        margin_factor=margin_factor,
        norm_margin=norm_margin,
    )

    # Tighten interval based on result
    tighten_interval(state, opponent_elo, result, norm_margin, expected)

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
    # Create a lookup for opponent ratings
    elo_lookup = {m[0]: m[2] for m in ranked_models}

    # Initialize fresh state
    state = init_placement_state(model_id, max_games)
    ensure_interval_bounds(state, ranked_models)

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
