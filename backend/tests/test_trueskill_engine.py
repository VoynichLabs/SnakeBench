import os
import sys
from unittest.mock import MagicMock

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.trueskill_engine import (
    TrueSkillEngine,
    DEFAULT_MU,
    DEFAULT_SIGMA,
)


def test_rate_game_updates_repository():
    mock_repo = MagicMock()
    mock_repo.get_participants_with_ratings.return_value = [
        {
            "model_id": 1,
            "model_name": "winner",
            "player_slot": 0,
            "score": 10,
            "result": "won",
            "trueskill_mu": DEFAULT_MU,
            "trueskill_sigma": DEFAULT_SIGMA,
            "trueskill_exposed": DEFAULT_MU - 3 * DEFAULT_SIGMA,
        },
        {
            "model_id": 2,
            "model_name": "loser",
            "player_slot": 1,
            "score": 5,
            "result": "lost",
            "trueskill_mu": DEFAULT_MU,
            "trueskill_sigma": DEFAULT_SIGMA,
            "trueskill_exposed": DEFAULT_MU - 3 * DEFAULT_SIGMA,
        },
    ]

    engine = TrueSkillEngine(model_repo=mock_repo)
    updates = engine.rate_game("game-1")

    mock_repo.get_participants_with_ratings.assert_called_once_with("game-1")
    mock_repo.update_trueskill_batch.assert_called_once()

    applied_updates = mock_repo.update_trueskill_batch.call_args[0][0]
    assert len(applied_updates) == 2
    assert updates == applied_updates

    winner = next(u for u in applied_updates if u["model_id"] == 1)
    loser = next(u for u in applied_updates if u["model_id"] == 2)

    # Winner should gain rating; loser should lose rating.
    assert winner["mu"] > DEFAULT_MU
    assert loser["mu"] < DEFAULT_MU
    # Display rating should be populated (alias for elo_rating during transition).
    assert "display_rating" in winner and winner["display_rating"] > 0


def test_rate_game_two_player_tie_is_symmetric():
    mock_repo = MagicMock()
    mock_repo.get_participants_with_ratings.return_value = [
        {
            "model_id": 1,
            "model_name": "alpha",
            "player_slot": 0,
            "score": 3,
            "result": "tied",
            "trueskill_mu": DEFAULT_MU,
            "trueskill_sigma": DEFAULT_SIGMA,
            "trueskill_exposed": DEFAULT_MU - 3 * DEFAULT_SIGMA,
        },
        {
            "model_id": 2,
            "model_name": "beta",
            "player_slot": 1,
            "score": 3,
            "result": "tied",
            "trueskill_mu": DEFAULT_MU,
            "trueskill_sigma": DEFAULT_SIGMA,
            "trueskill_exposed": DEFAULT_MU - 3 * DEFAULT_SIGMA,
        },
    ]

    engine = TrueSkillEngine(model_repo=mock_repo)
    updates = engine.rate_game("game-2", persist=False, log=False)

    # Expect symmetric updates for a tie: mu should remain very close and sigma should shrink.
    mu_values = [u["mu"] for u in updates]
    sigma_values = [u["sigma"] for u in updates]

    assert abs(mu_values[0] - mu_values[1]) < 1e-6
    assert sigma_values[0] < DEFAULT_SIGMA and sigma_values[1] < DEFAULT_SIGMA
