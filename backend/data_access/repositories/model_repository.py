"""
Model repository for model-related database operations.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional

from .base import BaseRepository


# ELO parameters (matching elo_tracker.py)
K = 32
INITIAL_RATING = 1500

# Result ranking
RESULT_RANK = {"won": 2, "tied": 1, "lost": 0}


def get_pair_result(result_i: str, result_j: str) -> tuple:
    """
    Given result strings for two players, return head-to-head scores.

    Returns:
        Tuple (S_i, S_j) where S = 1 means win, 0 means loss, 0.5 means tie.
    """
    rank_i = RESULT_RANK.get(result_i, 1)
    rank_j = RESULT_RANK.get(result_j, 1)
    if rank_i > rank_j:
        return 1, 0
    elif rank_i < rank_j:
        return 0, 1
    else:
        return 0.5, 0.5


def expected_score(rating_i: float, rating_j: float) -> float:
    """Compute the expected score for player i vs. player j."""
    return 1 / (1 + 10 ** ((rating_j - rating_i) / 400))


class ModelRepository(BaseRepository):
    """
    Repository for models table operations.
    """

    # -------------------------------------------------------------------------
    # Query operations
    # -------------------------------------------------------------------------

    def get_all(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """
        Get all models sorted by ELO rating.

        Args:
            active_only: If True, only return active models

        Returns:
            List of model dictionaries
        """
        with self.read_connection() as (conn, cursor):
            query = """
                SELECT
                    id, name, provider, model_slug, is_active, test_status,
                    elo_rating, wins, losses, ties, apples_eaten, games_played,
                    pricing_input, pricing_output, max_completion_tokens,
                    last_played_at, discovered_at
                FROM models
                WHERE name != 'Auto Router'
            """

            if active_only:
                query += " AND is_active = TRUE"

            query += " ORDER BY elo_rating DESC"

            cursor.execute(query)

            models = []
            for row in cursor.fetchall():
                models.append(self._row_to_model(row))

            return models

    def get_by_name(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a model by its name.

        Args:
            model_name: The model name to look up

        Returns:
            Model dictionary or None if not found
        """
        with self.read_connection() as (conn, cursor):
            cursor.execute("""
                SELECT
                    id, name, provider, model_slug, is_active, test_status,
                    elo_rating, wins, losses, ties, apples_eaten, games_played,
                    pricing_input, pricing_output, max_completion_tokens,
                    last_played_at, discovered_at
                FROM models
                WHERE name = %s AND name != 'Auto Router'
            """, (model_name,))

            row = cursor.fetchone()
            if row is None:
                return None

            return self._row_to_model(row)

    def get_by_id(self, model_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a model by its ID.

        Args:
            model_id: The model ID

        Returns:
            Model dictionary or None if not found
        """
        with self.read_connection() as (conn, cursor):
            cursor.execute("""
                SELECT
                    id, name, provider, model_slug, is_active, test_status,
                    elo_rating, wins, losses, ties, apples_eaten, games_played,
                    pricing_input, pricing_output, max_completion_tokens,
                    last_played_at, discovered_at
                FROM models
                WHERE id = %s
            """, (model_id,))

            row = cursor.fetchone()
            if row is None:
                return None

            return self._row_to_model(row)

    def get_ranked_models(self) -> List[Dict[str, Any]]:
        """
        Get all ranked and active models sorted by ELO.

        Returns:
            List of (id, name, elo_rating, rank_index) tuples
        """
        with self.read_connection() as (conn, cursor):
            cursor.execute("""
                SELECT id, name, elo_rating
                FROM models
                WHERE test_status = 'ranked' AND is_active = TRUE
                ORDER BY elo_rating DESC
            """)

            models = []
            for idx, row in enumerate(cursor.fetchall()):
                models.append({
                    'id': row['id'],
                    'name': row['name'],
                    'elo_rating': row['elo_rating'],
                    'rank_index': idx
                })

            return models

    # -------------------------------------------------------------------------
    # Update operations
    # -------------------------------------------------------------------------

    def update_elo(self, model_id: int, new_rating: float) -> None:
        """
        Update a model's ELO rating.

        Args:
            model_id: The model ID
            new_rating: The new ELO rating
        """
        with self.connection() as (conn, cursor):
            cursor.execute("""
                UPDATE models
                SET elo_rating = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (new_rating, model_id))

    def update_elo_ratings_for_game(self, game_id: str) -> None:
        """
        Update ELO ratings for all participants in a game using pairwise comparisons.

        Implements the same algorithm as elo_tracker.py process_game() function.

        Args:
            game_id: The game identifier to process
        """
        with self.connection() as (conn, cursor):
            # Get all participants with their current ELO ratings
            cursor.execute("""
                SELECT
                    gp.model_id, gp.result, m.elo_rating, m.name
                FROM game_participants gp
                JOIN models m ON gp.model_id = m.id
                WHERE gp.game_id = %s
                ORDER BY gp.player_slot
            """, (game_id,))

            participants = cursor.fetchall()

            if len(participants) < 2:
                print(f"Game {game_id} has fewer than 2 participants, skipping ELO update")
                return

            # Build data structures
            n = len(participants)
            model_ids = [p['model_id'] for p in participants]
            results = [p['result'] for p in participants]
            ratings = {p['model_id']: p['elo_rating'] for p in participants}
            names = {p['model_id']: p['name'] for p in participants}

            # Accumulate actual and expected scores (pairwise)
            score_sum = {mid: 0 for mid in model_ids}
            expected_sum = {mid: 0 for mid in model_ids}

            for i in range(n):
                for j in range(i + 1, n):
                    mid_i = model_ids[i]
                    mid_j = model_ids[j]

                    S_i, S_j = get_pair_result(results[i], results[j])
                    E_i = expected_score(ratings[mid_i], ratings[mid_j])
                    E_j = expected_score(ratings[mid_j], ratings[mid_i])

                    score_sum[mid_i] += S_i
                    score_sum[mid_j] += S_j
                    expected_sum[mid_i] += E_i
                    expected_sum[mid_j] += E_j

            # Update each model's ELO rating
            for mid in model_ids:
                delta = (K / (n - 1)) * (score_sum[mid] - expected_sum[mid]) if (n > 1) else 0
                new_rating = ratings[mid] + delta

                cursor.execute("""
                    UPDATE models
                    SET elo_rating = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (new_rating, mid))

                print(f"Updated ELO for {names[mid]}: {ratings[mid]:.2f} -> {new_rating:.2f} (delta: {delta:+.2f})")

    def update_aggregates_for_game(self, game_id: str) -> None:
        """
        Update model aggregate statistics for all participants in a game.

        Args:
            game_id: The game identifier to process
        """
        with self.connection() as (conn, cursor):
            cursor.execute("""
                SELECT
                    gp.model_id, gp.result, gp.score, m.name
                FROM game_participants gp
                JOIN models m ON gp.model_id = m.id
                WHERE gp.game_id = %s
            """, (game_id,))

            participants = cursor.fetchall()

            for participant in participants:
                model_id = participant['model_id']
                result = participant['result']
                score = participant['score']
                name = participant['name']

                win_delta = 1 if result == 'won' else 0
                loss_delta = 1 if result == 'lost' else 0
                tie_delta = 1 if result == 'tied' else 0

                cursor.execute("""
                    UPDATE models
                    SET wins = wins + %s,
                        losses = losses + %s,
                        ties = ties + %s,
                        apples_eaten = apples_eaten + %s,
                        games_played = games_played + 1,
                        last_played_at = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (
                    win_delta,
                    loss_delta,
                    tie_delta,
                    score,
                    datetime.now().isoformat(),
                    model_id
                ))

                print(f"Updated aggregates for {name}: +{score} apples, result={result}")

    def update_test_status(self, model_id: int, status: str) -> None:
        """
        Update a model's test status.

        Args:
            model_id: The model ID
            status: New status ('untested', 'testing', 'ranked', 'retired')
        """
        with self.connection() as (conn, cursor):
            cursor.execute("""
                UPDATE models
                SET test_status = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (status, model_id))

    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------

    def _row_to_model(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a database row to a model dictionary."""
        return {
            'id': row['id'],
            'name': row['name'],
            'provider': row['provider'],
            'model_slug': row['model_slug'],
            'model_name': row['model_slug'],  # Alias for LLM provider compatibility
            'is_active': row['is_active'],
            'test_status': row['test_status'],
            'elo_rating': row['elo_rating'],
            'wins': row['wins'],
            'losses': row['losses'],
            'ties': row['ties'],
            'apples_eaten': row['apples_eaten'],
            'games_played': row['games_played'],
            'pricing_input': row['pricing_input'],
            'pricing_output': row['pricing_output'],
            'max_completion_tokens': row['max_completion_tokens'],
            'last_played_at': row['last_played_at'],
            'discovered_at': row['discovered_at'],
            # Nested pricing dict for compatibility
            'pricing': {
                'input': float(row['pricing_input']) if row['pricing_input'] is not None else 0,
                'output': float(row['pricing_output']) if row['pricing_output'] is not None else 0,
            }
        }


# Singleton instance for convenience
model_repository = ModelRepository()
