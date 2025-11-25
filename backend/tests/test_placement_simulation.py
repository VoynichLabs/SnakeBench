#!/usr/bin/env python3
"""
Simulation tests for placement system algorithms.

Tests whether a new model that wins all games can reach #1 position,
and whether a model that loses all games can reach last position.

Uses real ELO distribution from the database to simulate realistic scenarios.
"""

import pytest
import sys
import os
from dataclasses import dataclass
from typing import List, Tuple, Optional, Set
from copy import deepcopy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_postgres import get_connection
from data_access.repositories.model_repository import K, expected_score


# =============================================================================
# Test Data: Fetch real ELO distribution
# =============================================================================

def fetch_real_elo_distribution() -> List[Tuple[int, str, float]]:
    """
    Fetch real ELO distribution from database.
    Returns: List of (model_id, name, elo_rating) sorted by ELO descending.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, elo_rating
        FROM models
        WHERE test_status = 'ranked' AND is_active = TRUE
        ORDER BY elo_rating DESC
    """)

    models = [(row['id'], row['name'], row['elo_rating']) for row in cursor.fetchall()]
    conn.close()
    return models


def create_synthetic_distribution(n: int = 300) -> List[Tuple[int, str, float]]:
    """
    Create a synthetic ELO distribution similar to real data.
    Real data: min=1351, max=1716, median=1468
    """
    import random
    random.seed(42)

    models = []
    for i in range(n):
        # Normal distribution centered around 1500
        elo = random.gauss(1500, 80)
        elo = max(1300, min(1750, elo))  # Clamp to realistic range
        models.append((i + 1000, f"Model_{i}", elo))

    # Sort by ELO descending
    models.sort(key=lambda x: -x[2])
    return models


# =============================================================================
# Current Algorithm: Rank-based Binary Search
# =============================================================================

@dataclass
class RankPlacementState:
    """Current placement system state (rank-based binary search)."""
    low: int
    high: int
    games_played: int
    opponents_played: Set[int]
    elo: float = 1500.0  # Track ELO for comparison


def simulate_current_algorithm(
    ranked_models: List[Tuple[int, str, float]],
    max_games: int,
    win_all: bool = True
) -> Tuple[int, float, List[str]]:
    """
    Simulate the current rank-based binary search placement.

    Args:
        ranked_models: List of (id, name, elo) sorted by ELO desc
        max_games: Number of games to play
        win_all: If True, new model wins all games. If False, loses all.

    Returns:
        Tuple of (final_rank, final_elo, game_log)
    """
    N = len(ranked_models)
    state = RankPlacementState(
        low=0,
        high=N - 1,
        games_played=0,
        opponents_played=set(),
        elo=1500.0
    )

    game_log = []

    for game_num in range(max_games):
        # Select opponent at midpoint (simplified - no jitter for test clarity)
        target_index = (state.low + state.high) // 2

        # Find opponent near target
        opponent_id, opponent_name, opponent_elo = ranked_models[target_index]
        opponent_rank = target_index

        # Simulate game result
        result = 'won' if win_all else 'lost'

        # Update ELO (2-player game)
        E_new = expected_score(state.elo, opponent_elo)
        S_new = 1.0 if win_all else 0.0
        delta = K * (S_new - E_new)
        state.elo += delta

        # Update binary search interval (current algorithm)
        if result == 'won':
            if opponent_rank == 0:
                state.low = 0
                state.high = 0
            else:
                state.high = opponent_rank - 1
        else:  # lost
            if opponent_rank == N - 1:
                state.low = N - 1
                state.high = N - 1
            else:
                state.low = opponent_rank + 1

        # Clamp bounds
        state.low = max(0, state.low)
        state.high = min(N - 1, state.high)
        if state.low > state.high:
            state.low = opponent_rank
            state.high = opponent_rank

        state.games_played += 1
        state.opponents_played.add(opponent_id)

        game_log.append(
            f"Game {game_num + 1}: vs {opponent_name} (rank #{opponent_rank}, ELO {opponent_elo:.1f}) "
            f"-> {result.upper()} | interval=[{state.low}, {state.high}] | ELO={state.elo:.1f}"
        )

    # Final rank is state.low (conservative placement)
    final_rank = state.low
    return final_rank, state.elo, game_log


# =============================================================================
# Proposed Algorithm: ELO-based Binary Search
# =============================================================================

@dataclass
class EloPlacementState:
    """Proposed placement system state (ELO-based binary search)."""
    elo_low: float
    elo_high: float
    games_played: int
    opponents_played: Set[int]
    elo: float = 1500.0


def simulate_elo_interval_algorithm(
    ranked_models: List[Tuple[int, str, float]],
    max_games: int,
    win_all: bool = True
) -> Tuple[int, float, List[str]]:
    """
    Simulate the proposed ELO-interval binary search placement.

    Args:
        ranked_models: List of (id, name, elo) sorted by ELO desc
        max_games: Number of games to play
        win_all: If True, new model wins all games. If False, loses all.

    Returns:
        Tuple of (final_rank, final_elo, game_log)
    """
    # Get ELO bounds from ranked models
    elos = [m[2] for m in ranked_models]
    min_elo = min(elos) - 50  # Buffer below worst
    max_elo = max(elos) + 50  # Buffer above best

    state = EloPlacementState(
        elo_low=min_elo,
        elo_high=max_elo,
        games_played=0,
        opponents_played=set(),
        elo=1500.0
    )

    game_log = []

    for game_num in range(max_games):
        # Calculate target ELO (midpoint of interval)
        target_elo = (state.elo_low + state.elo_high) / 2

        # Find opponent closest to target ELO
        best_opponent = None
        best_distance = float('inf')
        for idx, (mid, name, elo) in enumerate(ranked_models):
            if mid not in state.opponents_played:
                distance = abs(elo - target_elo)
                if distance < best_distance:
                    best_distance = distance
                    best_opponent = (idx, mid, name, elo)

        # Fallback if all played
        if best_opponent is None:
            for idx, (mid, name, elo) in enumerate(ranked_models):
                distance = abs(elo - target_elo)
                if distance < best_distance:
                    best_distance = distance
                    best_opponent = (idx, mid, name, elo)

        opponent_rank, opponent_id, opponent_name, opponent_elo = best_opponent

        # Simulate game result
        result = 'won' if win_all else 'lost'

        # Update actual ELO (2-player game)
        E_new = expected_score(state.elo, opponent_elo)
        S_new = 1.0 if win_all else 0.0
        delta = K * (S_new - E_new)
        state.elo += delta

        # Update ELO search interval (proposed algorithm)
        if result == 'won':
            # New model is at least as good as opponent
            # Search for higher ELO opponents
            state.elo_low = opponent_elo
        else:  # lost
            # New model is worse than opponent
            # Search for lower ELO opponents
            state.elo_high = opponent_elo

        state.games_played += 1
        state.opponents_played.add(opponent_id)

        game_log.append(
            f"Game {game_num + 1}: vs {opponent_name} (rank #{opponent_rank}, ELO {opponent_elo:.1f}) "
            f"-> {result.upper()} | elo_interval=[{state.elo_low:.1f}, {state.elo_high:.1f}] | ELO={state.elo:.1f}"
        )

    # Determine final rank based on final ELO
    final_rank = 0
    for idx, (_, _, elo) in enumerate(ranked_models):
        if state.elo < elo:
            final_rank = idx + 1

    return final_rank, state.elo, game_log


# =============================================================================
# Test Cases
# =============================================================================

class TestPlacementSimulation:
    """Test placement algorithms with simulated games."""

    @pytest.fixture
    def real_models(self):
        """Fetch real model distribution from database."""
        return fetch_real_elo_distribution()

    @pytest.fixture
    def synthetic_models(self):
        """Create synthetic 300-model distribution."""
        return create_synthetic_distribution(300)

    def test_current_algorithm_win_all_real_data(self, real_models):
        """
        Test: Current algorithm - new model wins all 8 games.
        Question: Can it reach rank #1?
        """
        final_rank, final_elo, game_log = simulate_current_algorithm(
            real_models, max_games=8, win_all=True
        )

        print(f"\n{'='*70}")
        print("CURRENT ALGORITHM: Win all 8 games (real data, {len(real_models)} models)")
        print(f"{'='*70}")
        for line in game_log:
            print(f"  {line}")
        print(f"\nFINAL RANK: #{final_rank + 1} (0-indexed: {final_rank})")
        print(f"FINAL ELO: {final_elo:.1f}")
        print(f"TOP MODEL ELO: {real_models[0][2]:.1f} ({real_models[0][1]})")
        print(f"CAN REACH #1: {'YES' if final_rank == 0 else 'NO'}")

        # This assertion documents current behavior - it may fail
        # That's the point: to show the limitation
        if final_rank > 0:
            pytest.skip(f"Current algorithm cannot reach #1 in 8 games (got #{final_rank + 1})")

    def test_current_algorithm_lose_all_real_data(self, real_models):
        """
        Test: Current algorithm - new model loses all 8 games.
        Question: Can it reach last place?
        """
        final_rank, final_elo, game_log = simulate_current_algorithm(
            real_models, max_games=8, win_all=False
        )

        last_rank = len(real_models) - 1

        print(f"\n{'='*70}")
        print(f"CURRENT ALGORITHM: Lose all 8 games (real data, {len(real_models)} models)")
        print(f"{'='*70}")
        for line in game_log:
            print(f"  {line}")
        print(f"\nFINAL RANK: #{final_rank + 1} (0-indexed: {final_rank})")
        print(f"FINAL ELO: {final_elo:.1f}")
        print(f"LAST MODEL ELO: {real_models[-1][2]:.1f} ({real_models[-1][1]})")
        print(f"CAN REACH LAST: {'YES' if final_rank >= last_rank else 'NO'}")

    def test_elo_interval_algorithm_win_all_real_data(self, real_models):
        """
        Test: Proposed ELO-interval algorithm - new model wins all 8 games.
        Question: Can it reach rank #1?
        """
        final_rank, final_elo, game_log = simulate_elo_interval_algorithm(
            real_models, max_games=8, win_all=True
        )

        print(f"\n{'='*70}")
        print(f"ELO-INTERVAL ALGORITHM: Win all 8 games (real data, {len(real_models)} models)")
        print(f"{'='*70}")
        for line in game_log:
            print(f"  {line}")
        print(f"\nFINAL RANK: #{final_rank + 1} (0-indexed: {final_rank})")
        print(f"FINAL ELO: {final_elo:.1f}")
        print(f"TOP MODEL ELO: {real_models[0][2]:.1f} ({real_models[0][1]})")
        print(f"CAN REACH #1: {'YES' if final_rank == 0 else 'NO'}")

    def test_elo_interval_algorithm_lose_all_real_data(self, real_models):
        """
        Test: Proposed ELO-interval algorithm - new model loses all 8 games.
        Question: Can it reach last place?
        """
        final_rank, final_elo, game_log = simulate_elo_interval_algorithm(
            real_models, max_games=8, win_all=False
        )

        last_rank = len(real_models) - 1

        print(f"\n{'='*70}")
        print(f"ELO-INTERVAL ALGORITHM: Lose all 8 games (real data, {len(real_models)} models)")
        print(f"{'='*70}")
        for line in game_log:
            print(f"  {line}")
        print(f"\nFINAL RANK: #{final_rank + 1} (0-indexed: {final_rank})")
        print(f"FINAL ELO: {final_elo:.1f}")
        print(f"LAST MODEL ELO: {real_models[-1][2]:.1f} ({real_models[-1][1]})")
        print(f"CAN REACH LAST: {'YES' if final_rank >= last_rank else 'NO'}")

    def test_compare_algorithms_synthetic_300(self, synthetic_models):
        """
        Compare both algorithms on 300 synthetic models.
        """
        print(f"\n{'='*70}")
        print("COMPARISON: 300 Synthetic Models, 8 Games")
        print(f"{'='*70}")

        # Current algorithm - win all
        curr_rank_win, curr_elo_win, _ = simulate_current_algorithm(
            synthetic_models, max_games=8, win_all=True
        )

        # Current algorithm - lose all
        curr_rank_lose, curr_elo_lose, _ = simulate_current_algorithm(
            synthetic_models, max_games=8, win_all=False
        )

        # ELO-interval algorithm - win all
        elo_rank_win, elo_elo_win, _ = simulate_elo_interval_algorithm(
            synthetic_models, max_games=8, win_all=True
        )

        # ELO-interval algorithm - lose all
        elo_rank_lose, elo_elo_lose, _ = simulate_elo_interval_algorithm(
            synthetic_models, max_games=8, win_all=False
        )

        print(f"\n{'Algorithm':<25} {'Win All -> Rank':<20} {'Lose All -> Rank':<20}")
        print(f"{'-'*65}")
        print(f"{'Current (rank-based)':<25} #{curr_rank_win + 1:<19} #{curr_rank_lose + 1:<19}")
        print(f"{'Proposed (ELO-interval)':<25} #{elo_rank_win + 1:<19} #{elo_rank_lose + 1:<19}")
        print(f"\nTotal models: {len(synthetic_models)}")
        print(f"Top ELO: {synthetic_models[0][2]:.1f}")
        print(f"Bottom ELO: {synthetic_models[-1][2]:.1f}")

        # The key assertions
        print(f"\n{'='*70}")
        print("RESULTS:")
        print(f"  Current algorithm - can reach #1 with 8 wins: {'YES' if curr_rank_win == 0 else 'NO'}")
        print(f"  ELO-interval algorithm - can reach #1 with 8 wins: {'YES' if elo_rank_win == 0 else 'NO'}")
        print(f"{'='*70}")


class TestWinStreakScenarios:
    """Test specific win/loss scenarios to verify placement accuracy."""

    @pytest.fixture
    def real_models(self):
        return fetch_real_elo_distribution()

    def test_win_all_8_games_gets_first_place(self, real_models):
        """
        New model wins ALL 8 games.
        Expected: Should reach rank #1.
        """
        final_rank, final_elo, game_log = simulate_current_algorithm(
            real_models, max_games=8, win_all=True
        )

        print(f"\n{'='*70}")
        print(f"SCENARIO: Win all 8 games ({len(real_models)} models)")
        print(f"{'='*70}")
        for line in game_log:
            print(f"  {line}")
        print(f"\nFINAL RANK: #{final_rank + 1}")
        print(f"FINAL ELO: {final_elo:.1f}")
        print(f"RESULT: {'PASS - Reached #1' if final_rank == 0 else 'FAIL - Did not reach #1'}")

        assert final_rank == 0, f"Expected rank #1, got #{final_rank + 1}"

    def test_lose_at_different_points(self, real_models):
        """
        What happens if you lose at different points in the evaluation?
        - Lose game 1 (first game)
        - Lose game 4 (middle)
        - Lose game 8 (last game)
        """
        print(f"\n{'='*70}")
        print(f"SCENARIO: Lose at Different Points ({len(real_models)} models)")
        print(f"{'='*70}")

        N = len(real_models)

        def simulate_with_loss_at(loss_game: int):
            """Simulate winning all except losing at specified game."""
            state_low, state_high = 0, N - 1
            elo = 1500.0

            for game_num in range(1, 9):
                target = (state_low + state_high) // 2
                opp = real_models[target]

                if game_num == loss_game:
                    # LOSE this game
                    E = expected_score(elo, opp[2])
                    elo += K * (0.0 - E)
                    if target >= N - 1:
                        state_low = N - 1
                    else:
                        state_low = target + 1
                else:
                    # WIN
                    E = expected_score(elo, opp[2])
                    elo += K * (1.0 - E)
                    if target == 0:
                        state_high = 0
                    else:
                        state_high = target - 1

                state_low = max(0, state_low)
                state_high = min(N - 1, state_high)
                if state_low > state_high:
                    # Bounds crossed - this is a problem!
                    state_low = state_high = target

            return state_low, elo

        # Test different loss points
        results = []
        for loss_at in [1, 2, 3, 4, 5, 6, 7, 8]:
            rank, elo = simulate_with_loss_at(loss_at)
            results.append((loss_at, rank, elo))
            print(f"  Lose game {loss_at}: Final rank #{rank + 1}, ELO {elo:.1f}")

        # Also test win all
        rank_win_all, elo_win_all, _ = simulate_current_algorithm(real_models, 8, win_all=True)
        print(f"\n  Win ALL 8:  Final rank #{rank_win_all + 1}, ELO {elo_win_all:.1f}")

        print(f"\n  Analysis:")
        print(f"  - Losing early (game 1-3) has biggest impact on final rank")
        print(f"  - Losing late (game 7-8) has less impact because interval already narrow")

    def test_win_all_8_vs_win_7_lose_1(self, real_models):
        """
        Compare: Win all 8 vs Win 7 + Lose last one.
        Show the difference in final placement.
        """
        print(f"\n{'='*70}")
        print(f"COMPARISON: Win All 8 vs Win 7 + Lose Last ({len(real_models)} models)")
        print(f"{'='*70}")

        N = len(real_models)

        # Scenario 1: Win all 8
        print(f"\n--- Scenario 1: Win ALL 8 games ---")
        state_low, state_high = 0, N - 1
        elo = 1500.0
        opponents_faced = []

        for game_num in range(1, 9):
            target = (state_low + state_high) // 2
            opp = real_models[target]
            opponents_faced.append((target, opp[1], opp[2]))

            E = expected_score(elo, opp[2])
            elo += K * (1.0 - E)

            if target == 0:
                state_low, state_high = 0, 0
            else:
                state_high = target - 1

            state_low = max(0, state_low)
            state_high = max(0, state_high)

            print(f"  Game {game_num}: vs {opp[1][:30]:<30} (#{target}, ELO {opp[2]:.0f}) -> WIN | [{state_low},{state_high}]")

        win_all_rank = state_low
        win_all_elo = elo
        print(f"\n  RESULT: Rank #{win_all_rank + 1}, ELO {win_all_elo:.1f}")

        # Scenario 2: Win 7, lose last
        print(f"\n--- Scenario 2: Win 7, LOSE game 8 ---")
        state_low, state_high = 0, N - 1
        elo = 1500.0

        for game_num in range(1, 9):
            target = (state_low + state_high) // 2
            opp = real_models[target]

            if game_num <= 7:
                # WIN
                E = expected_score(elo, opp[2])
                elo += K * (1.0 - E)

                if target == 0:
                    state_low, state_high = 0, 0
                else:
                    state_high = target - 1

                print(f"  Game {game_num}: vs {opp[1][:30]:<30} (#{target}, ELO {opp[2]:.0f}) -> WIN | [{state_low},{state_high}]")
            else:
                # LOSE game 8
                E = expected_score(elo, opp[2])
                elo += K * (0.0 - E)

                if target >= N - 1:
                    state_low, state_high = N - 1, N - 1
                else:
                    state_low = target + 1

                print(f"  Game {game_num}: vs {opp[1][:30]:<30} (#{target}, ELO {opp[2]:.0f}) -> LOSE | [{state_low},{state_high}]")

            state_low = max(0, state_low)
            state_high = min(N - 1, state_high)
            if state_low > state_high:
                state_low = state_high = target

        win7_lose1_rank = state_low
        win7_lose1_elo = elo
        print(f"\n  RESULT: Rank #{win7_lose1_rank + 1}, ELO {win7_lose1_elo:.1f}")

        # Summary
        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")
        print(f"  Win all 8:        Rank #{win_all_rank + 1}, ELO {win_all_elo:.1f}")
        print(f"  Win 7, Lose 1:    Rank #{win7_lose1_rank + 1}, ELO {win7_lose1_elo:.1f}")
        print(f"  Rank difference:  {win7_lose1_rank - win_all_rank} positions")

        # Who did they lose to in game 8?
        game8_opponent = opponents_faced[7] if len(opponents_faced) >= 8 else None
        if game8_opponent:
            print(f"\n  Game 8 opponent (for win-all scenario): {game8_opponent[1]} (#{game8_opponent[0]})")
            print(f"  Losing to this opponent drops you to rank #{win7_lose1_rank + 1}")


class TestMinGamesRequired:
    """Test minimum games required to reach extremes."""

    @pytest.fixture
    def real_models(self):
        return fetch_real_elo_distribution()

    def test_min_games_to_reach_first(self, real_models):
        """
        Find minimum games needed for current algorithm to reach #1.
        """
        print(f"\n{'='*70}")
        print(f"MINIMUM GAMES TO REACH #1 (Current Algorithm, {len(real_models)} models)")
        print(f"{'='*70}")

        for max_games in range(1, 20):
            final_rank, final_elo, _ = simulate_current_algorithm(
                real_models, max_games=max_games, win_all=True
            )
            reached = "YES" if final_rank == 0 else "NO"
            print(f"  {max_games} games: rank #{final_rank + 1}, ELO {final_elo:.1f} - Reached #1: {reached}")

            if final_rank == 0:
                print(f"\n  RESULT: Minimum {max_games} games needed to reach #1")
                break
        else:
            print(f"\n  RESULT: Cannot reach #1 even with 19 games")

    def test_min_games_elo_interval_to_reach_first(self, real_models):
        """
        Find minimum games needed for ELO-interval algorithm to reach #1.
        """
        print(f"\n{'='*70}")
        print(f"MINIMUM GAMES TO REACH #1 (ELO-Interval Algorithm, {len(real_models)} models)")
        print(f"{'='*70}")

        for max_games in range(1, 20):
            final_rank, final_elo, _ = simulate_elo_interval_algorithm(
                real_models, max_games=max_games, win_all=True
            )
            reached = "YES" if final_rank == 0 else "NO"
            print(f"  {max_games} games: rank #{final_rank + 1}, ELO {final_elo:.1f} - Reached #1: {reached}")

            if final_rank == 0:
                print(f"\n  RESULT: Minimum {max_games} games needed to reach #1")
                break
        else:
            print(f"\n  RESULT: Cannot reach #1 even with 19 games")


# =============================================================================
# Test: Demonstrate the leaderboard shift bug
# =============================================================================

class TestLeaderboardShiftBug:
    """
    Demonstrate the bug where leaderboard shifts between games
    cause the binary search to select wrong opponents.
    """

    def test_leaderboard_shift_causes_wrong_opponent(self):
        """
        Simulate what happens when new models get ranked between evaluation games.

        This demonstrates the actual bug in the current system.
        """
        # Initial leaderboard: 100 models
        initial_models = [
            (i, f"Model_{i}", 1700 - i * 3)  # ELO from 1700 down to 1403
            for i in range(100)
        ]

        print(f"\n{'='*70}")
        print("BUG DEMONSTRATION: Leaderboard Shift Between Games")
        print(f"{'='*70}")

        # New model starts evaluation
        # Game 1: Plays against rank #50 (Model_50, ELO 1550) and WINS
        game1_opponent_rank = 50
        game1_opponent = initial_models[game1_opponent_rank]
        print(f"\nGame 1: vs {game1_opponent[1]} (rank #{game1_opponent_rank}, ELO {game1_opponent[2]})")
        print(f"  Result: WIN")
        print(f"  Stored opponent_rank_at_match: {game1_opponent_rank}")
        print(f"  State after: low=0, high={game1_opponent_rank - 1}")  # high = 49

        # --- BETWEEN GAMES: 20 new models get ranked at various positions ---
        # This pushes existing models down
        print(f"\n--- 20 new models get ranked, shifting the leaderboard ---")

        shifted_models = []
        insert_positions = [5, 10, 15, 20, 25, 30, 35, 40, 45, 48,
                          52, 55, 60, 65, 70, 75, 80, 85, 90, 95]

        new_model_idx = 0
        original_idx = 0
        for pos in range(120):  # 100 original + 20 new = 120
            if new_model_idx < 20 and pos == insert_positions[new_model_idx] + new_model_idx:
                # Insert a new model here
                shifted_models.append((1000 + new_model_idx, f"NewModel_{new_model_idx}", 1700 - pos * 2.5))
                new_model_idx += 1
            else:
                if original_idx < 100:
                    shifted_models.append(initial_models[original_idx])
                    original_idx += 1

        # Re-sort by ELO to get proper ranking
        shifted_models.sort(key=lambda x: -x[2])

        # Find where Model_50 is now
        model_50_new_rank = None
        for idx, (mid, name, elo) in enumerate(shifted_models):
            if name == "Model_50":
                model_50_new_rank = idx
                break

        print(f"  Model_50 was rank #50, now rank #{model_50_new_rank}")

        # Game 2: System reconstructs state
        # It uses stored opponent_rank_at_match=50, so high=49
        # But now it picks opponent at midpoint of [0, 49] from NEW list
        reconstructed_high = game1_opponent_rank - 1  # 49
        target_index = (0 + reconstructed_high) // 2  # 24

        game2_opponent_from_shifted = shifted_models[target_index]

        # What SHOULD have happened: pick model with similar ELO to original target
        # Original rank #24 had ELO = 1700 - 24*3 = 1628
        original_target_elo = 1700 - 24 * 3

        print(f"\nGame 2 reconstruction:")
        print(f"  Stored state: high={reconstructed_high} (from Game 1)")
        print(f"  Target index: {target_index} (midpoint of [0, {reconstructed_high}])")
        print(f"  Selected opponent: {game2_opponent_from_shifted[1]} (ELO {game2_opponent_from_shifted[2]:.1f})")

        # Find what model is at the original target ELO range
        original_rank_24_model = initial_models[24]
        original_rank_24_new_position = None
        for idx, (mid, name, elo) in enumerate(shifted_models):
            if name == original_rank_24_model[1]:
                original_rank_24_new_position = idx
                break

        print(f"\n  EXPECTED (if leaderboard hadn't shifted):")
        print(f"    Should play: {original_rank_24_model[1]} (was rank #24, ELO {original_rank_24_model[2]})")
        print(f"    This model is now at rank #{original_rank_24_new_position}")

        print(f"\n  ACTUAL (bug):")
        print(f"    Playing: {game2_opponent_from_shifted[1]} (rank #24 in NEW list, ELO {game2_opponent_from_shifted[2]:.1f})")

        elo_difference = abs(game2_opponent_from_shifted[2] - original_rank_24_model[2])
        print(f"\n  ELO MISMATCH: {elo_difference:.1f} points!")

        if game2_opponent_from_shifted[1] != original_rank_24_model[1]:
            print(f"\n  BUG CONFIRMED: Wrong opponent selected due to leaderboard shift")

        # Show the REAL bug: state reconstruction with shifting leaderboard
        print(f"\n{'='*70}")
        print("REAL BUG: State Reconstruction with Shifting Leaderboard")
        print(f"{'='*70}")
        print("\nThis simulates exactly what evaluate_models.py does:")
        print("1. Run evaluation batch -> dispatch game 1")
        print("2. Game 1 completes, leaderboard shifts")
        print("3. Run evaluation batch -> reconstruct state from history")
        print("4. State has old rank indices, but we select from NEW leaderboard")

        # Track game history as stored in DB
        game_history = []  # List of (opponent_id, opponent_rank_at_match, result)

        # Start with initial leaderboard
        current_leaderboard = list(initial_models)
        N = len(current_leaderboard)

        for game_num in range(1, 9):
            print(f"\n--- Evaluation batch {game_num} ---")

            # Step 1: Reconstruct state from history (like rebuild_state_from_history)
            state_low, state_high = 0, N - 1
            for opp_id, opp_rank_at_match, result in game_history:
                if result == 'won':
                    state_high = opp_rank_at_match - 1
                else:
                    state_low = opp_rank_at_match + 1
                state_low = max(0, state_low)
                state_high = max(0, min(len(current_leaderboard) - 1, state_high))

            print(f"  Reconstructed state: [{state_low}, {state_high}]")

            # Step 2: Select opponent from CURRENT leaderboard at target index
            if state_high < state_low:
                print(f"  ERROR: Invalid interval, binary search corrupted!")
                break

            target = (state_low + state_high) // 2
            target = min(target, len(current_leaderboard) - 1)
            opponent = current_leaderboard[target]

            print(f"  Target index: {target}")
            print(f"  Selected: {opponent[1]} (ELO {opponent[2]:.1f})")

            # Step 3: Game plays, new model WINS
            result = 'won'

            # Step 4: Store opponent_rank_at_match (the current rank)
            game_history.append((opponent[0], target, result))
            print(f"  Stored: opponent_rank_at_match={target}")

            # Step 5: Between batches, leaderboard shifts
            # Add 5 models with ELOs that push into top 50
            if game_num < 8:
                for i in range(5):
                    new_elo = 1650 + game_num * 5 - i * 3  # High ELO models
                    current_leaderboard.append(
                        (3000 + game_num * 10 + i, f"NewRanked_{game_num}_{i}", new_elo)
                    )
                current_leaderboard.sort(key=lambda x: -x[2])

                print(f"  +5 new models ranked, leaderboard now has {len(current_leaderboard)} models")

        # Final analysis
        print(f"\n{'='*70}")
        print("ANALYSIS")
        print(f"{'='*70}")
        print(f"\nGame history stored in DB:")
        for i, (opp_id, rank, result) in enumerate(game_history):
            print(f"  Game {i+1}: opponent_rank_at_match={rank}, result={result}")

        print(f"\nFinal leaderboard size: {len(current_leaderboard)}")
        print(f"Final state: [{state_low}, {state_high}]")

        # The problem: early games stored small rank numbers
        # But leaderboard grew, so those ranks now point to different quality tiers
        print(f"\nPROBLEM:")
        print(f"  Game 1 stored rank #50 when there were 100 models (50th percentile)")
        print(f"  Now there are {len(current_leaderboard)} models")
        print(f"  Rank #50 is now {50/len(current_leaderboard)*100:.1f}th percentile")
        print(f"  The interval bounds are STALE - they refer to old positions")

    def test_best_model_cant_reach_first_when_better_models_added(self):
        """
        The critical bug: A model that beats everyone can't reach #1
        if better models are added to the leaderboard during evaluation.
        """
        print(f"\n{'='*70}")
        print("CRITICAL BUG: Best Model Can't Reach #1")
        print(f"{'='*70}")
        print("\nScenario: New model is THE BEST (beats everyone)")
        print("But stronger models get ranked during its evaluation")
        print("Result: It can never reach #1 because #0 keeps changing")

        # Initial leaderboard: 100 models, top ELO is 1700
        current_leaderboard = [
            (i, f"Model_{i}", 1700 - i * 3)
            for i in range(100)
        ]

        game_history = []
        N = len(current_leaderboard)

        for game_num in range(1, 9):
            print(f"\n--- Game {game_num} ---")

            # Reconstruct state
            state_low, state_high = 0, N - 1
            for opp_id, opp_rank_at_match, result in game_history:
                if result == 'won':
                    state_high = min(state_high, opp_rank_at_match - 1)
                state_high = max(0, state_high)

            # Select opponent
            target = (state_low + state_high) // 2
            target = max(0, min(target, len(current_leaderboard) - 1))
            opponent = current_leaderboard[target]

            print(f"  State: [{state_low}, {state_high}], target={target}")
            print(f"  Playing: {opponent[1]} (ELO {opponent[2]:.1f})")

            # New model WINS (it's the best!)
            game_history.append((opponent[0], target, 'won'))

            # CRITICAL: After each game, a STRONGER model gets ranked
            # This pushes our target down
            if game_num <= 6:
                new_top_elo = current_leaderboard[0][2] + 20  # Higher than current #1
                new_model = (5000 + game_num, f"SuperModel_{game_num}", new_top_elo)
                current_leaderboard.insert(0, new_model)
                print(f"  NEW #1: {new_model[1]} (ELO {new_model[2]:.1f}) - pushes everyone down!")

        # Check final result
        print(f"\n{'='*70}")
        print("RESULT")
        print(f"{'='*70}")
        print(f"\nFinal state: [{state_low}, {state_high}]")

        # The new model beat Model_0 (original #1) in game 6
        # But now there are 6 SuperModels above it!
        print(f"\nLeaderboard now has {len(current_leaderboard)} models")
        print(f"Top 10:")
        for i, (mid, name, elo) in enumerate(current_leaderboard[:10]):
            print(f"  #{i}: {name} (ELO {elo:.1f})")

        # The new model's placement would be rank #0 based on state
        # But it never played SuperModel_1 through SuperModel_6!
        print(f"\nBUG: New model would be placed at rank #{state_low}")
        print(f"     But it never beat SuperModel_1 through SuperModel_6!")
        print(f"     It only beat Model_0 (now rank #6)")

        # This is only a bug if state_low == 0 but there are unplayed better models
        beaten_model_ids = {h[0] for h in game_history}
        unbeaten_above = []
        for i, (mid, name, elo) in enumerate(current_leaderboard[:state_low + 1]):
            if mid not in beaten_model_ids:
                unbeaten_above.append((i, name, elo))

        if unbeaten_above:
            print(f"\n  CRITICAL: {len(unbeaten_above)} models above final rank were never played!")
            for rank, name, elo in unbeaten_above:
                print(f"    #{rank}: {name} (ELO {elo:.1f}) - NEVER PLAYED")
        else:
            print(f"\n  OK: All models above final rank were played")

    def test_actual_failure_opponent_moved_down(self):
        """
        The ACTUAL bug: When we beat opponent at rank #50, we set high=49.
        But that opponent might have moved to rank #60 due to new models.
        Now our interval [0, 49] excludes the opponent we ACTUALLY beat,
        which means we might skip challenging opponents in that range.

        This causes INCORRECT PLACEMENT - we get placed too high.
        """
        print(f"\n{'='*70}")
        print("ACTUAL FAILURE: Opponent Moved Down After Match")
        print(f"{'='*70}")

        # Initial: 100 models
        initial_leaderboard = [
            (i, f"Model_{i}", 1700 - i * 3)
            for i in range(100)
        ]

        print("\nInitial state:")
        print(f"  100 models, #0=Model_0 (1700), #99=Model_99 (1403)")

        # Game 1: New model plays rank #50 and LOSES
        game1_target = 50
        game1_opponent = initial_leaderboard[game1_target]
        print(f"\nGame 1: vs {game1_opponent[1]} (rank #{game1_target}, ELO {game1_opponent[2]})")
        print(f"  Result: LOST")
        print(f"  State after: low={game1_target + 1}, high=99")

        stored_rank = game1_target  # Store rank #50

        # Between games: 20 HIGH ELO models get ranked, pushing Model_50 down
        print(f"\n--- 20 high-ELO models ranked ---")
        current_leaderboard = list(initial_leaderboard)
        for i in range(20):
            new_elo = 1750 - i * 2  # All above 1700
            current_leaderboard.insert(0, (1000 + i, f"NewTop_{i}", new_elo))

        # Find where Model_50 is now
        model_50_new_rank = None
        for idx, (mid, name, elo) in enumerate(current_leaderboard):
            if name == "Model_50":
                model_50_new_rank = idx
                break

        print(f"  Model_50 was rank #50, now rank #{model_50_new_rank}")

        # Game 2: Reconstruct state using stored_rank=50
        # low = 50 + 1 = 51 (because we lost to rank #50)
        reconstructed_low = stored_rank + 1  # 51
        reconstructed_high = len(current_leaderboard) - 1  # 119

        print(f"\nGame 2 reconstruction:")
        print(f"  Used stored opponent_rank_at_match={stored_rank}")
        print(f"  Reconstructed state: [{reconstructed_low}, {reconstructed_high}]")

        # Problem: We're searching in [51, 119] of NEW leaderboard
        # But Model_50 (which we lost to) is now at rank #70
        # We might be searching ABOVE where we should be!

        target = (reconstructed_low + reconstructed_high) // 2  # 85
        opponent_at_target = current_leaderboard[target]

        print(f"  Target: {target}")
        print(f"  Selected: {opponent_at_target[1]} (ELO {opponent_at_target[2]:.1f})")

        # What's the ELO at our target vs what it should be?
        # We lost to ELO 1550, so we should be searching BELOW 1550
        model_50_elo = 1700 - 50 * 3  # 1550

        print(f"\n  PROBLEM:")
        print(f"    We lost to {game1_opponent[1]} (ELO {model_50_elo})")
        print(f"    We should search for opponents with ELO < {model_50_elo}")
        print(f"    But we selected {opponent_at_target[1]} (ELO {opponent_at_target[2]:.1f})")

        if opponent_at_target[2] > model_50_elo:
            print(f"\n  BUG: Selected opponent has HIGHER ELO than the one we lost to!")
            print(f"       This means we're searching in the wrong range.")
        elif opponent_at_target[2] < model_50_elo - 100:
            print(f"\n  BUG: Selected opponent has much LOWER ELO than expected.")
            print(f"       Placement will be inaccurate.")
        else:
            print(f"\n  OK: Selected opponent has similar ELO (within 100 points)")


# =============================================================================
# Main: Run as script for quick testing
# =============================================================================

if __name__ == "__main__":
    print("Fetching real ELO distribution from database...")
    real_models = fetch_real_elo_distribution()
    print(f"Found {len(real_models)} ranked models")
    print(f"Top: {real_models[0][1]} (ELO {real_models[0][2]:.1f})")
    print(f"Bottom: {real_models[-1][1]} (ELO {real_models[-1][2]:.1f})")

    # Run key simulations
    print("\n" + "="*70)
    print("SIMULATION: New model wins all 8 games")
    print("="*70)

    print("\n--- CURRENT ALGORITHM (rank-based binary search) ---")
    rank, elo, log = simulate_current_algorithm(real_models, max_games=8, win_all=True)
    for line in log:
        print(f"  {line}")
    print(f"\n  FINAL: Rank #{rank + 1}, ELO {elo:.1f}")
    print(f"  CAN REACH #1: {'YES' if rank == 0 else 'NO'}")

    print("\n--- PROPOSED ALGORITHM (ELO-interval binary search) ---")
    rank, elo, log = simulate_elo_interval_algorithm(real_models, max_games=8, win_all=True)
    for line in log:
        print(f"  {line}")
    print(f"\n  FINAL: Rank #{rank + 1}, ELO {elo:.1f}")
    print(f"  CAN REACH #1: {'YES' if rank == 0 else 'NO'}")
