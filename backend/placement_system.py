"""
Simplified Placement System

Uses TrueSkill ratings from the database (updated by trueskill_engine after
every game) instead of maintaining parallel custom rating math.  The placement
system only handles:
  - Bookkeeping: tracking opponents played, game history, rematch logic
  - Opponent selection: targeting models near the evaluated model's own rating,
    breaking ties by information gain
"""

from typing import Optional, Tuple, Set, List, Dict, Any
from dataclasses import dataclass
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database_postgres import get_connection
from services.trueskill_engine import (
    DEFAULT_MU as TS_DEFAULT_MU,
    DEFAULT_SIGMA as TS_DEFAULT_SIGMA,
)


# =============================================================================
# Configuration
# =============================================================================

# Maximum rematches allowed per opponent
MAX_REMATCHES = 1

# Minimum rating delta upward after a win (avoid replaying same/lower while on a climb)
MIN_ASCEND_RATING_DELTA = 0.01

# Frontier providers whose models should preferentially play each other
FRONTIER_PROVIDERS = frozenset({'openai', 'anthropic', 'google', 'xai', 'meta'})

# Info-gain multiplier when opponent is a frontier provider
FRONTIER_BONUS = 1.5

# Hard cap: never play the same opponent more than this many times during placement
MAX_PLACEMENT_REPEATS = 2


# =============================================================================
# Placement State
# =============================================================================

@dataclass
class PlacementState:
    """
    State tracking for placement.

    mu/sigma come from the DB (written by trueskill_engine after each game).
    This class only does bookkeeping for opponent selection.
    """
    model_id: int
    mu: float
    sigma: float
    games_played: int
    max_games: int
    opponents_played: Set[int]
    opponent_play_counts: Dict[int, int]
    game_history: List[Dict[str, Any]]
    pending_rematch: Optional[int] = None

    @property
    def exposed(self) -> float:
        """Conservative TrueSkill rating (mu - 3*sigma)."""
        return self.mu - 3.0 * self.sigma

    def __post_init__(self):
        if self.opponent_play_counts is None:
            self.opponent_play_counts = {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'model_id': self.model_id,
            'mu': self.mu,
            'sigma': self.sigma,
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
        # Support legacy format that stored skill as a sub-dict
        skill = data.get('skill', {})
        return cls(
            model_id=data['model_id'],
            mu=data.get('mu', skill.get('mu', TS_DEFAULT_MU)),
            sigma=data.get('sigma', skill.get('sigma', TS_DEFAULT_SIGMA)),
            games_played=data.get('games_played', 0),
            max_games=data.get('max_games', 9),
            opponents_played=set(data.get('opponents_played', [])),
            opponent_play_counts=data.get('opponent_play_counts', {}),
            game_history=data.get('game_history', []),
            pending_rematch=data.get('pending_rematch'),
        )


# =============================================================================
# DB helpers
# =============================================================================

def _read_model_trueskill(model_id: int) -> Tuple[float, float]:
    """Read current trueskill_mu and trueskill_sigma from the DB."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT trueskill_mu, trueskill_sigma FROM models WHERE id = %s",
            (model_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return TS_DEFAULT_MU, TS_DEFAULT_SIGMA
        return (
            row.get('trueskill_mu') or TS_DEFAULT_MU,
            row.get('trueskill_sigma') or TS_DEFAULT_SIGMA,
        )
    finally:
        conn.close()


# =============================================================================
# Core Functions
# =============================================================================

def get_ranked_models_by_index() -> List[Dict[str, Any]]:
    """
    Get all ranked models sorted by conservative TrueSkill (exposed).

    Returns:
        List of dicts with keys:
            id, name, rating, rank_index, pricing_input, pricing_output, provider
        where rank_index 0 = best, N-1 = worst
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, name, trueskill_exposed, pricing_input, pricing_output, provider
            FROM models
            WHERE test_status = 'ranked' AND is_active = TRUE
            ORDER BY trueskill_exposed DESC NULLS LAST
        """)

        models = cursor.fetchall()
        return [
            {
                'id': m['id'],
                'name': m['name'],
                'rating': m.get('trueskill_exposed') or 0.0,
                'rank_index': idx,
                'pricing_input': m.get('pricing_input'),
                'pricing_output': m.get('pricing_output'),
                'provider': m.get('provider'),
            }
            for idx, m in enumerate(models)
        ]

    finally:
        conn.close()


def init_placement_state(model_id: int, max_games: int = 9) -> PlacementState:
    """
    Initialize placement state for a model, reading current mu/sigma from DB.
    """
    mu, sigma = _read_model_trueskill(model_id)
    return PlacementState(
        model_id=model_id,
        mu=mu,
        sigma=sigma,
        games_played=0,
        max_games=max_games,
        opponents_played=set(),
        opponent_play_counts={},
        game_history=[],
        pending_rematch=None,
    )


def calculate_information_gain(
    mu: float,
    sigma: float,
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
        mu: Current model's TrueSkill mu
        sigma: Current model's TrueSkill sigma
        opponent_rating: Rating of potential opponent (TrueSkill exposed)
        opponent_id: ID of potential opponent
        play_count: How many times we've played this opponent

    Returns:
        Information gain score (higher = more informative)
    """
    repeat_penalty = 0.1 ** play_count  # 1.0, 0.1, 0.01, ...

    distance_from_estimate = abs(opponent_rating - mu)
    optimal_distance = sigma * 0.5

    if sigma > 0:
        distance_factor = math.exp(-((distance_from_estimate - optimal_distance) ** 2) / (2 * sigma ** 2))
    else:
        distance_factor = 1.0 if distance_from_estimate < 50 else 0.0

    uncertainty_factor = sigma / TS_DEFAULT_SIGMA

    return repeat_penalty * distance_factor * (0.5 + 0.5 * uncertainty_factor)


def should_rematch(
    result: str,
    my_score: int,
    opponent_score: int,
    opponent_id: int,
    play_count: int
) -> bool:
    """
    Determine if we should rematch this opponent.

    Rematch when loss is by <= 1 apple and we haven't exceeded max rematches.
    """
    if result != 'lost':
        return False

    if play_count >= MAX_REMATCHES + 1:
        return False

    score_diff = abs(my_score - opponent_score)
    return score_diff <= 1


def _pricing_target(
    model_pricing: Optional[Tuple[float, float]],
    ranked_models: List[Dict[str, Any]],
) -> float:
    """
    Compute a target rating based on pricing similarity.

    Finds ranked models within ~0.5 log10 of the evaluated model's cost
    (same order of magnitude) and returns the median rating of that cohort.
    Falls back to the overall median rating if no pricing data or no matches.
    """
    all_ratings = [m['rating'] for m in ranked_models]
    if not all_ratings:
        return 0.0
    overall_median = sorted(all_ratings)[len(all_ratings) // 2]

    if model_pricing is None:
        return overall_median

    p_in, p_out = model_pricing
    model_cost = (p_in or 0) + (p_out or 0)
    if model_cost <= 0:
        return overall_median

    log_model = math.log10(model_cost)

    cohort_ratings = []
    for m in ranked_models:
        mp_in = m.get('pricing_input') or 0
        mp_out = m.get('pricing_output') or 0
        m_cost = float(mp_in) + float(mp_out)
        if m_cost <= 0:
            continue
        if abs(math.log10(m_cost) - log_model) <= 0.5:
            cohort_ratings.append(m['rating'])

    if not cohort_ratings:
        return overall_median

    cohort_ratings.sort()
    return cohort_ratings[len(cohort_ratings) // 2]


def select_next_opponent(
    state: PlacementState,
    ranked_models: Optional[List[Dict[str, Any]]] = None
) -> Optional[Dict[str, Any]]:
    opponent, _ = select_next_opponent_with_reason(state, ranked_models=ranked_models)
    return opponent


def select_next_opponent_with_reason(
    state: PlacementState,
    ranked_models: Optional[List[Dict[str, Any]]] = None,
    model_pricing: Optional[Tuple[float, float]] = None,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Select the next opponent.

    Strategy:
    1. If there's a pending rematch, do that first
    2. Blend pricing-based target (early) with TrueSkill-based target (later)
    3. Score candidates by distance to target, tie-break by info gain
    4. Hard cap: skip opponents played >= MAX_PLACEMENT_REPEATS times
    5. Frontier bonus: multiply info gain for frontier provider opponents
    6. After a win, prefer strictly higher-rated opponents

    Args:
        state: Current placement state
        ranked_models: List of ranked model dicts
        model_pricing: Optional (pricing_input, pricing_output) for the evaluated model
    """
    debug: Dict[str, Any] = {}

    if state.games_played >= state.max_games:
        return None, debug

    if ranked_models is None:
        ranked_models = get_ranked_models_by_index()

    if not ranked_models:
        print("  No ranked models available for placement")
        return None, debug

    candidates = [m for m in ranked_models if m['id'] != state.model_id]

    if not candidates:
        return None, debug

    # Check for pending rematch
    if state.pending_rematch is not None:
        for m in candidates:
            if m['id'] == state.pending_rematch:
                debug.update({
                    "reason": "pending_rematch",
                    "opponent_id": m['id'],
                })
                return m, debug
        state.pending_rematch = None

    # Hard cap: remove opponents already played MAX_PLACEMENT_REPEATS times
    candidates = [
        m for m in candidates
        if state.opponent_play_counts.get(m['id'], 0) < MAX_PLACEMENT_REPEATS
    ]
    if not candidates:
        return None, debug

    # If we just won, prefer strictly higher-rated opponents to keep climbing
    last_game = state.game_history[-1] if state.game_history else None
    last_win_rating = None
    if last_game and last_game.get("result") == "won":
        last_win_rating = last_game.get("opponent_rating")

    filtered_candidates = candidates
    if last_win_rating is not None:
        upward = [c for c in candidates if c['rating'] > last_win_rating + MIN_ASCEND_RATING_DELTA]
        if upward:
            filtered_candidates = upward
            debug["ascend_filter_from"] = last_win_rating
            debug["ascend_filter_count"] = len(upward)

    candidates = filtered_candidates

    # Blended target: pricing-based early, TrueSkill-based later
    pricing_target = _pricing_target(model_pricing, ranked_models)
    alpha = min(state.games_played / 4.0, 1.0)  # 0→pricing, 1→rating
    target_rating = alpha * state.exposed + (1 - alpha) * pricing_target
    debug["target_rating"] = target_rating
    debug["pricing_target"] = pricing_target
    debug["alpha"] = alpha

    # Score each candidate by distance to target, breaking ties with information gain
    best = None
    best_key = None
    for m in candidates:
        model_id = m['id']
        name = m['name']
        rating = m['rating']
        rank = m['rank_index']
        play_count = state.opponent_play_counts.get(model_id, 0)
        info_gain = calculate_information_gain(state.mu, state.sigma, rating, model_id, play_count)

        # Frontier bonus
        provider = (m.get('provider') or '').lower()
        if provider in FRONTIER_PROVIDERS:
            info_gain *= FRONTIER_BONUS

        distance = abs(rating - target_rating)
        key = (distance, -info_gain)
        if best is None or key < best_key:
            best = m
            best_key = key
            debug.update({
                "selected_id": model_id,
                "selected_name": name,
                "selected_rating": rating,
                "selected_rank": rank,
                "distance_to_target": distance,
                "info_gain": info_gain,
                "play_count": play_count,
            })

    return best, debug


def update_placement_state(
    state: PlacementState,
    game_result: Dict[str, Any],
    opponent_rating: float
) -> None:
    """
    Update placement state after a completed game.

    Only does bookkeeping — TrueSkill mu/sigma are already updated in the DB
    by trueskill_engine.rate_game().  We re-read them here.
    """
    opponent_id = game_result['opponent_id']
    result = game_result['result']
    my_score = game_result.get('my_score', 0)
    opponent_score = game_result.get('opponent_score', 0)

    # Re-read mu/sigma from DB (already updated by trueskill_engine)
    state.mu, state.sigma = _read_model_trueskill(state.model_id)

    # Track opponent
    state.opponents_played.add(opponent_id)
    state.opponent_play_counts[opponent_id] = state.opponent_play_counts.get(opponent_id, 0) + 1

    # Add to history
    state.game_history.append({
        **game_result,
        'opponent_rating': opponent_rating,
    })

    # Increment games played
    state.games_played += 1

    # Clear any pending rematch (we just played it)
    if state.pending_rematch == opponent_id:
        state.pending_rematch = None

    # Check if we should request a rematch (loss by <= 1 apple)
    play_count = state.opponent_play_counts[opponent_id]
    if should_rematch(result, my_score, opponent_score, opponent_id, play_count):
        state.pending_rematch = opponent_id
        print(f"  Close loss (score diff <= 1) - scheduling rematch")


def get_final_rank(
    state: PlacementState,
    ranked_models: Optional[List[Dict[str, Any]]] = None
) -> int:
    """
    Determine final rank based on exposed rating.

    Compares the model's exposed rating against all ranked models.
    """
    if ranked_models is None:
        ranked_models = get_ranked_models_by_index()

    if not ranked_models:
        return 0

    final_rank = 0
    for idx, m in enumerate(ranked_models):
        if state.exposed < m['rating']:
            final_rank = idx + 1

    return final_rank


def rebuild_state_from_history(
    model_id: int,
    max_games: int,
    history: List[Dict[str, Any]],
    ranked_models: List[Dict[str, Any]]
) -> Tuple[PlacementState, int]:
    """
    Reconstruct placement state from completed evaluation games.

    Only replays bookkeeping (opponents played, history, game count).
    Reads current mu/sigma from DB instead of replaying custom math.
    """
    rating_lookup = {m['id']: m['rating'] for m in ranked_models}

    # Read current mu/sigma from DB
    mu, sigma = _read_model_trueskill(model_id)

    state = PlacementState(
        model_id=model_id,
        mu=mu,
        sigma=sigma,
        games_played=0,
        max_games=max_games,
        opponents_played=set(),
        opponent_play_counts={},
        game_history=[],
        pending_rematch=None,
    )

    for record in history:
        opponent_id = record.get('opponent_id')
        result = record.get('model_result') or record.get('result')

        if opponent_id is None or result is None:
            continue

        opponent_rating = record.get('opponent_rating') or record.get('opponent_elo')
        if opponent_rating is None:
            opponent_rating = rating_lookup.get(opponent_id, TS_DEFAULT_MU)

        my_score = record.get('my_score', 0)
        opponent_score = record.get('opponent_score', 0)

        # Track opponent
        state.opponents_played.add(opponent_id)
        state.opponent_play_counts[opponent_id] = state.opponent_play_counts.get(opponent_id, 0) + 1

        # Add to history
        state.game_history.append({
            'opponent_id': opponent_id,
            'result': result,
            'my_score': my_score,
            'opponent_score': opponent_score,
            'my_death_reason': record.get('my_death_reason'),
            'total_rounds': record.get('total_rounds', 50),
            'opponent_rating': opponent_rating,
        })

        state.games_played += 1

        # Replay rematch logic for the last game
        play_count = state.opponent_play_counts[opponent_id]
        if should_rematch(result, my_score, opponent_score, opponent_id, play_count):
            state.pending_rematch = opponent_id
        elif state.pending_rematch == opponent_id:
            state.pending_rematch = None

    return state, len(history)


# =============================================================================
# Utility Functions
# =============================================================================

def get_opponent_rank_index(
    opponent_id: int,
    ranked_models: Optional[List[Dict[str, Any]]] = None
) -> Optional[int]:
    """Get the current rank index of an opponent."""
    if ranked_models is None:
        ranked_models = get_ranked_models_by_index()

    for m in ranked_models:
        if m['id'] == opponent_id:
            return m['rank_index']

    return None


def format_state_summary(state: PlacementState) -> str:
    """Format a human-readable summary of placement state."""
    return (
        f"Skill: mu={state.mu:.1f} sigma={state.sigma:.1f} exposed={state.exposed:.1f} | "
        f"Games: {state.games_played}/{state.max_games}"
    )
