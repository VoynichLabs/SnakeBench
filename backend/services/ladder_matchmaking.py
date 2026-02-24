"""
Ladder matchmaking — schedules games between ranked models so ratings
continue to evolve after placement is complete.

Called periodically by cron_service.  Dispatches games via the existing
Celery run_game_task.

Scoring uses a blend of:
  - Rating closeness (nearby-skill matchups are most informative)
  - Pricing similarity (similarly-priced models should play each other)
  - Sigma priority (uncertain models benefit most from games)
Frontier-provider pairs get reserved slots each cycle.
"""

import logging
import math
import random
from typing import Dict, List, Set, Tuple, Any

from data_access.repositories import ModelRepository
from data_access.api_queries import get_model_by_name
from tasks import run_game_task

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_CONCURRENT_LADDER_GAMES = 10
GAMES_PER_CYCLE = 8
RECENT_PAIR_HOURS = 24
MAX_RECENT_PAIR_GAMES = 3

# Game board parameters (match evaluation defaults)
LADDER_GAME_PARAMS: Dict[str, Any] = {
    "width": 10,
    "height": 10,
    "max_rounds": 100,
    "num_apples": 5,
    "game_type": "ladder",
}

# Fraction of pairs selected randomly to explore cross-ladder matchups
RANDOM_PAIR_FRACTION = 0.30

# Frontier providers that should preferentially play each other
FRONTIER_PROVIDERS = frozenset({'openai', 'anthropic', 'google', 'xai', 'meta'})

# Minimum frontier-vs-frontier games reserved per cycle
MIN_FRONTIER_GAMES = 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log_cost(model: Dict) -> float:
    """Return log10 of total pricing (input + output), or 0.0 if missing."""
    p_in = model.get('pricing_input') or 0
    p_out = model.get('pricing_output') or 0
    total = float(p_in) + float(p_out)
    if total <= 0:
        return 0.0
    return math.log10(total)


def _is_frontier(model: Dict) -> bool:
    return (model.get('provider') or '').lower() in FRONTIER_PROVIDERS


def _pair_score(a: Dict, b: Dict) -> float:
    """
    Score a candidate pair.  Higher = better matchup.

    Blend of:
      0.5 * rating_closeness  (nearby skill)
      0.3 * pricing_similarity (similar cost tier)
      0.2 * sigma_priority     (uncertain models benefit most)
    """
    rating_a = a.get('trueskill_exposed') or 0
    rating_b = b.get('trueskill_exposed') or 0
    rating_closeness = 1.0 / (1 + abs(rating_a - rating_b))

    log_a = _log_cost(a)
    log_b = _log_cost(b)
    # If either has no pricing data, treat as neutral (0.5)
    if log_a == 0.0 or log_b == 0.0:
        pricing_similarity = 0.5
    else:
        pricing_similarity = 1.0 / (1 + abs(log_a - log_b))

    sigma_a = a.get('trueskill_sigma') or 0
    sigma_b = b.get('trueskill_sigma') or 0
    sigma_priority = (sigma_a + sigma_b) / 2.0 / 8.333  # normalise by default sigma

    return 0.5 * rating_closeness + 0.3 * pricing_similarity + 0.2 * min(sigma_priority, 1.0)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def dispatch_ladder_games() -> Dict[str, Any]:
    """
    Select and dispatch a batch of ladder games between ranked models.

    Returns a summary dict with keys:
        dispatched: list of {model_a, model_b, task_id}
        in_flight: current in-flight count before dispatching
        skipped_reason: str or None
    """
    repo = ModelRepository()
    result: Dict[str, Any] = {"dispatched": [], "in_flight": 0, "skipped_reason": None}

    # 1. Throttle: check current in-flight ladder games
    in_flight = repo.count_in_flight_ladder_games()
    result["in_flight"] = in_flight
    if in_flight >= MAX_CONCURRENT_LADDER_GAMES:
        result["skipped_reason"] = f"in_flight={in_flight} >= max={MAX_CONCURRENT_LADDER_GAMES}"
        logger.info("Ladder matchmaking throttled: %s", result["skipped_reason"])
        return result

    budget = min(GAMES_PER_CYCLE, MAX_CONCURRENT_LADDER_GAMES - in_flight)

    # 2. Load ranked models (now includes pricing + provider)
    ranked = repo.get_ranked_models()
    if len(ranked) < 2:
        result["skipped_reason"] = "fewer than 2 ranked models"
        logger.info("Ladder matchmaking skipped: %s", result["skipped_reason"])
        return result

    # 3. Build saturated-pair set
    recent_pairs = repo.get_recent_ladder_pairs(hours=RECENT_PAIR_HOURS)
    saturated: Set[Tuple[int, int]] = set()
    for rp in recent_pairs:
        if rp['game_count'] >= MAX_RECENT_PAIR_GAMES:
            saturated.add((rp['model_id_a'], rp['model_id_b']))

    def _is_valid_pair(a: Dict, b: Dict) -> bool:
        pair_key = (min(a['id'], b['id']), max(a['id'], b['id']))
        return pair_key not in saturated

    # 4. Generate candidate pairs
    #    Walk the leaderboard with gap=1 (adjacent), gap=2 (skip-1), gap=3 (skip-2)
    candidate_pairs: List[Tuple[Dict, Dict]] = []
    for gap in (1, 2, 3):
        for i in range(len(ranked) - gap):
            a = ranked[i]
            b = ranked[i + gap]
            if _is_valid_pair(a, b):
                candidate_pairs.append((a, b))

    if not candidate_pairs:
        result["skipped_reason"] = "all candidate pairs saturated"
        logger.info("Ladder matchmaking skipped: %s", result["skipped_reason"])
        return result

    # 5. Select matchups
    selected: List[Tuple[Dict, Dict]] = []
    used_models: Set[int] = set()

    # 5a. Frontier-vs-frontier reserved slots
    frontier_pairs: List[Tuple[Dict, Dict]] = []
    for i in range(len(ranked)):
        for j in range(i + 1, len(ranked)):
            a, b = ranked[i], ranked[j]
            if _is_frontier(a) and _is_frontier(b) and _is_valid_pair(a, b):
                frontier_pairs.append((a, b))

    # Sort frontier pairs by blended score (best first)
    frontier_pairs.sort(key=lambda p: _pair_score(p[0], p[1]), reverse=True)

    frontier_budget = min(MIN_FRONTIER_GAMES, budget)
    for a, b in frontier_pairs:
        if len(selected) >= frontier_budget:
            break
        if a['id'] not in used_models and b['id'] not in used_models:
            selected.append((a, b))
            used_models.add(a['id'])
            used_models.add(b['id'])

    # 5b. Random exploration pairs (30% of remaining budget)
    remaining_budget = budget - len(selected)
    random_budget = max(1, int(remaining_budget * RANDOM_PAIR_FRACTION))

    all_valid_pairs: List[Tuple[Dict, Dict]] = []
    for i in range(len(ranked)):
        for j in range(i + 1, len(ranked)):
            a, b = ranked[i], ranked[j]
            if _is_valid_pair(a, b):
                all_valid_pairs.append((a, b))

    random.shuffle(all_valid_pairs)
    for a, b in all_valid_pairs:
        if len(selected) >= len(selected) + random_budget:
            break
        random_filled = len(selected) - frontier_budget
        if random_filled >= random_budget:
            break
        if a['id'] not in used_models and b['id'] not in used_models:
            selected.append((a, b))
            used_models.add(a['id'])
            used_models.add(b['id'])

    # 5c. Structured pairs: scored by blended pair_score
    candidate_pairs.sort(key=lambda p: _pair_score(p[0], p[1]), reverse=True)

    for a, b in candidate_pairs:
        if len(selected) >= budget:
            break
        if a['id'] not in used_models and b['id'] not in used_models:
            selected.append((a, b))
            used_models.add(a['id'])
            used_models.add(b['id'])

    # 6. Dispatch selected games
    for model_a, model_b in selected:
        try:
            config_a = get_model_by_name(model_a['name'])
            config_b = get_model_by_name(model_b['name'])

            if config_a is None or config_b is None:
                logger.warning(
                    "Could not load configs for ladder game: %s vs %s",
                    model_a['name'], model_b['name'],
                )
                continue

            task = run_game_task.apply_async(
                args=[config_a, config_b, LADDER_GAME_PARAMS],
            )

            result["dispatched"].append({
                "model_a": model_a['name'],
                "model_b": model_b['name'],
                "task_id": task.id,
            })
            logger.info(
                "Dispatched ladder game: %s vs %s (task=%s)",
                model_a['name'], model_b['name'], task.id,
            )
        except Exception:
            logger.exception(
                "Failed to dispatch ladder game: %s vs %s",
                model_a['name'], model_b['name'],
            )

    return result
