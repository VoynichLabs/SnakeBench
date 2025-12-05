from __future__ import annotations

"""
TrueSkill rating engine wrapper.

Encapsulates the TrueSkill environment and provides a single entrypoint
to rate a completed game by fetching participants, applying updates, and
writing mu/sigma back to the models table (with the ELO alias populated
from the conservative display score).
"""

from dataclasses import dataclass
from typing import List, Dict, Any

from trueskill import TrueSkill, Rating

from data_access.repositories import ModelRepository

# Fixed configuration for this deployment (keep in code, not env vars)
DEFAULT_MU = 25.0
DEFAULT_SIGMA = DEFAULT_MU / 3.0  # ~8.333
DEFAULT_BETA = DEFAULT_MU / 6.0
DEFAULT_TAU = 0.5
DEFAULT_DRAW_PROBABILITY = 0.1
DISPLAY_MULTIPLIER = 50.0  # Scales conservative rating into the UI-friendly number

# Result ranking (lower is better)
RESULT_RANK = {"won": 0, "tied": 1, "lost": 2}


@dataclass
class ParticipantState:
    model_id: int
    model_name: str
    player_slot: int
    result: str
    score: int
    rating: Rating


class TrueSkillEngine:
    """
    Wraps the TrueSkill environment and provides helpers for conservative
    rating and display scaling.
    """

    def __init__(
        self,
        model_repo: ModelRepository | None = None,
        env: TrueSkill | None = None,
    ) -> None:
        self.model_repo = model_repo or ModelRepository()
        self.env = env or TrueSkill(
            mu=DEFAULT_MU,
            sigma=DEFAULT_SIGMA,
            beta=DEFAULT_BETA,
            tau=DEFAULT_TAU,
            draw_probability=DEFAULT_DRAW_PROBABILITY,
        )

    def conservative_rating(self, rating: Rating) -> float:
        return rating.mu - 3.0 * rating.sigma

    def display_score(self, rating: Rating) -> float:
        return self.conservative_rating(rating) * DISPLAY_MULTIPLIER

    def _rank_from_result(self, result: str) -> int:
        """
        Map result strings to TrueSkill ranks (0 is best). Defaults to tie.
        """
        return RESULT_RANK.get(result or "tied", RESULT_RANK["tied"])

    def _load_participants(self, game_id: str) -> List[ParticipantState]:
        participants = self.model_repo.get_participants_with_ratings(game_id)
        states: List[ParticipantState] = []

        for row in participants:
            mu = row.get("trueskill_mu") or DEFAULT_MU
            sigma = row.get("trueskill_sigma") or DEFAULT_SIGMA

            states.append(
                ParticipantState(
                    model_id=row["model_id"],
                    model_name=row.get("model_name") or "unknown",
                    player_slot=row["player_slot"],
                    result=row["result"],
                    score=row.get("score", 0),
                    rating=self.env.Rating(mu=mu, sigma=sigma),
                )
            )

        return states

    def _compute_updates(self, participants: List[ParticipantState]) -> List[Dict[str, Any]]:
        """
        Compute TrueSkill updates for a set of participants.
        """
        teams = [[p.rating] for p in participants]
        ranks = [self._rank_from_result(p.result) for p in participants]

        rated_teams = self.env.rate(teams, ranks=ranks)

        updates = []
        for participant, rated_team in zip(participants, rated_teams):
            pre_rating = participant.rating
            pre_exposed = self.conservative_rating(pre_rating)
            pre_display = self.display_score(pre_rating)

            new_rating = rated_team[0]
            conservative = self.conservative_rating(new_rating)
            display_rating = self.display_score(new_rating)

            updates.append(
                {
                    "model_id": participant.model_id,
                    "model_name": participant.model_name,
                    "player_slot": participant.player_slot,
                    "score": participant.score,
                    "result": participant.result,
                    "pre_mu": pre_rating.mu,
                    "pre_sigma": pre_rating.sigma,
                    "pre_exposed": pre_exposed,
                    "pre_display_rating": pre_display,
                    "mu": new_rating.mu,
                    "sigma": new_rating.sigma,
                    "exposed": conservative,
                    "display_rating": display_rating,
                    "delta_mu": new_rating.mu - pre_rating.mu,
                    "delta_sigma": new_rating.sigma - pre_rating.sigma,
                    "delta_exposed": conservative - pre_exposed,
                    "delta_display_rating": display_rating - pre_display,
                }
            )

        return updates

    def rate_game(self, game_id: str, persist: bool = True, log: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch participants for a game, run TrueSkill updates, and persist
        new ratings (including the ELO compatibility alias) back to models.
        """
        participants = self._load_participants(game_id)

        if len(participants) < 2:
            print(f"Game {game_id} has fewer than 2 participants; skipping TrueSkill update.")
            return []

        updates = self._compute_updates(participants)

        if persist:
            self.model_repo.update_trueskill_batch(updates)

        if log:
            for u in updates:
                print(
                    f"Updated TrueSkill for {u['model_name']} "
                    f"(mu={u['mu']:.3f}, sigma={u['sigma']:.3f}, exposed={u['exposed']:.3f}, display={u['display_rating']:.1f})"
                )

        return updates


# Singleton instance for convenience
trueskill_engine = TrueSkillEngine()
