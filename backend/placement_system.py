"""
Binary search placement system for new model ranking.

Implements a binary search algorithm to efficiently place new models in the
leaderboard by playing exactly 10 games against strategically chosen opponents.
"""

from typing import Optional, Tuple, Set, List
from dataclasses import dataclass
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database_postgres import get_connection


@dataclass
class PlacementState:
    """State tracking for binary search placement."""
    model_id: int
    low: int  # Lower bound rank index (inclusive)
    high: int  # Upper bound rank index (inclusive)
    games_played: int
    max_games: int
    opponents_played: Set[int]

    def to_dict(self):
        """Convert to dictionary for database storage."""
        return {
            'model_id': self.model_id,
            'low': self.low,
            'high': self.high,
            'games_played': self.games_played,
            'max_games': self.max_games,
            'opponents_played': list(self.opponents_played)
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Create from dictionary loaded from database."""
        return cls(
            model_id=data['model_id'],
            low=data['low'],
            high=data['high'],
            games_played=data['games_played'],
            max_games=data['max_games'],
            opponents_played=set(data['opponents_played'])
        )


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
        # Add rank index to each model
        return [(m['id'], m['name'], m['elo_rating'], idx)
                for idx, m in enumerate(models)]

    finally:
        conn.close()


def init_placement_state(model_id: int, max_games: int = 10) -> PlacementState:
    """
    Initialize placement state for a new model.

    Args:
        model_id: ID of the model to place
        max_games: Number of games to play (default: 10)

    Returns:
        Initialized PlacementState
    """
    ranked_models = get_ranked_models_by_index()
    N = len(ranked_models)

    if N == 0:
        # No ranked models yet, place at index 0
        return PlacementState(
            model_id=model_id,
            low=0,
            high=0,
            games_played=0,
            max_games=max_games,
            opponents_played=set()
        )

    return PlacementState(
        model_id=model_id,
        low=0,
        high=N - 1,
        games_played=0,
        max_games=max_games,
        opponents_played=set()
    )


def select_opponent_at_index(
    target_index: int,
    ranked_models: List[Tuple[int, str, float, int]],
    placement_state: PlacementState
) -> Optional[Tuple[int, str, float, int]]:
    """
    Select an opponent near the target index, preferring unplayed opponents.

    Args:
        target_index: Desired rank index
        ranked_models: List of all ranked models
        placement_state: Current placement state

    Returns:
        Tuple of (model_id, name, elo_rating, rank_index) or None
    """
    if not ranked_models:
        return None

    # Filter out the test model itself
    candidates = [m for m in ranked_models if m[0] != placement_state.model_id]

    if not candidates:
        return None

    # Constrain target_index to valid range
    low_idx = placement_state.low
    high_idx = placement_state.high
    target_index = max(low_idx, min(high_idx, target_index))

    # Filter candidates within the current interval [low, high]
    interval_candidates = [m for m in candidates if low_idx <= m[3] <= high_idx]

    if not interval_candidates:
        # If no candidates in interval, use all candidates
        interval_candidates = candidates

    # Separate into played and unplayed
    unplayed = [m for m in interval_candidates if m[0] not in placement_state.opponents_played]

    # Prefer unplayed opponents
    pool = unplayed if unplayed else interval_candidates

    # Find closest to target_index
    best_candidate = min(pool, key=lambda m: abs(m[3] - target_index))

    return best_candidate


def select_next_opponent(
    placement_state: PlacementState,
    ranked_models: Optional[List[Tuple[int, str, float, int]]] = None
) -> Optional[Tuple[int, str, float]]:
    """
    Select the next opponent for placement using binary search strategy.

    Args:
        placement_state: Current placement state

    Returns:
        Tuple of (opponent_id, opponent_name, opponent_elo) or None
    """
    if placement_state.games_played >= placement_state.max_games:
        return None

    ranked_models = ranked_models if ranked_models is not None else get_ranked_models_by_index()

    if not ranked_models:
        print("  ⚠️  No ranked models available for placement")
        return None

    # Calculate midpoint of current interval
    target_index = (placement_state.low + placement_state.high) // 2

    # Select opponent near midpoint
    opponent = select_opponent_at_index(target_index, ranked_models, placement_state)

    if not opponent:
        return None

    opponent_id, opponent_name, opponent_elo, _ = opponent
    return (opponent_id, opponent_name, opponent_elo)


def update_placement_interval(
    placement_state: PlacementState,
    opponent_rank_index: int,
    result: str
) -> None:
    """
    Update the placement interval based on game result.

    Args:
        placement_state: Current placement state (modified in place)
        opponent_rank_index: Rank index of the opponent just played
        result: Game result from new model's perspective ('won', 'lost', 'tied')
    """
    N = len(get_ranked_models_by_index())

    if result == 'won':
        # New model is at least as good as opponent
        # They should rank above or equal to opponent
        if opponent_rank_index == 0:
            # Already beat the best, place at top
            placement_state.low = 0
            placement_state.high = 0
        else:
            # Place above this opponent
            placement_state.high = opponent_rank_index - 1

    elif result == 'lost':
        # New model is below opponent
        # They should rank below opponent
        if opponent_rank_index == N - 1:
            # Lost to worst, place at bottom
            placement_state.low = N - 1
            placement_state.high = N - 1
        else:
            # Place below this opponent
            placement_state.low = opponent_rank_index + 1

    else:  # tied
        # Roughly similar skill, narrow interval around opponent
        margin = 3  # ranks to consider similar
        placement_state.low = max(placement_state.low, opponent_rank_index - margin)
        placement_state.high = min(placement_state.high, opponent_rank_index + margin)

    # Clamp to valid range
    placement_state.low = max(0, placement_state.low)
    placement_state.high = min(N - 1, placement_state.high)

    # Handle crossed bounds
    if placement_state.low > placement_state.high:
        placement_state.low = opponent_rank_index
        placement_state.high = opponent_rank_index

    # Increment games played
    placement_state.games_played += 1


def get_opponent_rank_index(opponent_id: int, ranked_models: Optional[List[Tuple[int, str, float, int]]] = None) -> Optional[int]:
    """
    Get the current rank index of an opponent.

    Args:
        opponent_id: ID of the opponent model

    Returns:
        Rank index (0 = best)
    """
    ranked_models = ranked_models if ranked_models is not None else get_ranked_models_by_index()

    for model_id, _, _, rank_index in ranked_models:
        if model_id == opponent_id:
            return rank_index

    # Unknown opponent (not currently ranked/active)
    return None


def finalize_placement(placement_state: PlacementState) -> int:
    """
    Determine the final rank index for the new model.

    Args:
        placement_state: Final placement state

    Returns:
        Final rank index where model should be inserted
    """
    # Use the lower bound as the final position
    # This is conservative - if uncertain, rank them lower
    return placement_state.low


def save_placement_state(placement_state: PlacementState) -> None:
    """
    Save placement state to database.

    Args:
        placement_state: State to save
    """
    # Storage layer removed with evaluation queue deprecation.
    # Keep a no-op to preserve interface if called inadvertently.
    return


def load_placement_state(model_id: int) -> Optional[PlacementState]:
    """
    Load placement state from database.

    Args:
        model_id: ID of the model

    Returns:
        PlacementState if found, None otherwise
    """
    # Storage layer removed; return None to signal no persisted state.
    return None
