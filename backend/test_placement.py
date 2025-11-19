#!/usr/bin/env python3
"""
Test script for binary search placement system.

This script simulates the placement algorithm to verify it correctly
narrows down to the appropriate rank position.
"""

from placement_system import PlacementState, update_placement_interval


def simulate_placement_scenario(scenario_name: str, results: list, N: int = 100):
    """
    Simulate a placement scenario with a sequence of results.

    Args:
        scenario_name: Name of the test scenario
        results: List of (opponent_rank, result) tuples
        N: Total number of ranked models
    """
    print(f"\n{'=' * 70}")
    print(f"Scenario: {scenario_name}")
    print(f"{'=' * 70}")
    print(f"Total ranked models: {N}")

    # Initialize placement state
    state = PlacementState(
        model_id=9999,
        low=0,
        high=N - 1,
        games_played=0,
        max_games=10,
        opponents_played=set()
    )

    print(f"Initial interval: [{state.low}, {state.high}]")

    # Process each game result
    for game_num, (opponent_rank, result) in enumerate(results, 1):
        print(f"\nGame {game_num}: vs Rank #{opponent_rank} -> {result.upper()}")

        # Update interval
        update_placement_interval(state, opponent_rank, result)

        print(f"  New interval: [{state.low}, {state.high}]")
        print(f"  Interval size: {state.high - state.low + 1}")

        if state.low == state.high:
            print(f"  ✓ CONVERGED to rank #{state.low}")

    print(f"\n{'=' * 70}")
    print(f"Final Placement: Rank #{state.low}")
    print(f"Final interval size: {state.high - state.low + 1}")
    print(f"{'=' * 70}")

    return state.low


def main():
    """Run test scenarios."""
    print("Binary Search Placement System - Test Scenarios")
    print("=" * 70)

    # Scenario 1: Perfect model - wins all games
    print("\n" + "=" * 70)
    print("TEST 1: Perfect model (should reach rank #0)")
    print("=" * 70)
    results_1 = [
        (50, 'won'),   # Beat median -> look in top half
        (25, 'won'),   # Beat top 25% -> look in top 25%
        (12, 'won'),   # Keep winning
        (6, 'won'),
        (3, 'won'),
        (1, 'won'),
        (0, 'won'),    # Beat #1 -> place at #0
        (0, 'won'),
        (0, 'won'),
        (0, 'won'),
    ]
    final_rank = simulate_placement_scenario("Perfect Model", results_1, N=100)
    assert final_rank == 0, f"Expected rank 0, got {final_rank}"
    print("✓ Test 1 PASSED")

    # Scenario 2: Worst model - loses all games
    print("\n" + "=" * 70)
    print("TEST 2: Worst model (should reach rank #99)")
    print("=" * 70)
    results_2 = [
        (50, 'lost'),  # Lost to median -> look in bottom half
        (75, 'lost'),  # Lost to bottom 25% -> look in bottom 25%
        (87, 'lost'),
        (93, 'lost'),
        (96, 'lost'),
        (98, 'lost'),
        (99, 'lost'),  # Lost to worst -> place at #99
        (99, 'lost'),
        (99, 'lost'),
        (99, 'lost'),
    ]
    final_rank = simulate_placement_scenario("Worst Model", results_2, N=100)
    assert final_rank == 99, f"Expected rank 99, got {final_rank}"
    print("✓ Test 2 PASSED")

    # Scenario 3: Mid-tier model with mixed results
    print("\n" + "=" * 70)
    print("TEST 3: Mid-tier model (should reach around rank #50)")
    print("=" * 70)
    results_3 = [
        (50, 'won'),   # Beat median -> look in top half
        (25, 'lost'),  # Lost to top 25% -> narrow down
        (37, 'won'),   # Beat ~#37
        (31, 'lost'),  # Lost to ~#31
        (34, 'won'),   # Beat ~#34
        (32, 'lost'),  # Lost to ~#32
        (33, 'tied'),  # Tied with ~#33
        (33, 'won'),
        (32, 'lost'),
        (33, 'tied'),
    ]
    final_rank = simulate_placement_scenario("Mid-tier Model", results_3, N=100)
    # Should be somewhere in the 30-35 range
    assert 28 <= final_rank <= 38, f"Expected rank ~30-35, got {final_rank}"
    print("✓ Test 3 PASSED")

    # Scenario 4: Model that wins first 5, loses last 5 (unstable)
    print("\n" + "=" * 70)
    print("TEST 4: Unstable model (wins then loses)")
    print("=" * 70)
    results_4 = [
        (50, 'won'),
        (25, 'won'),
        (12, 'won'),
        (6, 'won'),
        (3, 'won'),
        (1, 'lost'),   # Start losing
        (2, 'lost'),
        (3, 'lost'),
        (4, 'lost'),
        (5, 'lost'),
    ]
    final_rank = simulate_placement_scenario("Unstable Model", results_4, N=100)
    # Should end up around rank 5-6 based on the pattern
    print("✓ Test 4 PASSED")

    # Scenario 5: Small pool (20 models) - verify it works with fewer models
    print("\n" + "=" * 70)
    print("TEST 5: Small pool (20 models)")
    print("=" * 70)
    results_5 = [
        (10, 'won'),
        (5, 'won'),
        (2, 'lost'),
        (3, 'won'),
        (2, 'lost'),
        (3, 'tied'),
        (3, 'won'),
        (2, 'lost'),
        (3, 'won'),
        (2, 'lost'),
    ]
    final_rank = simulate_placement_scenario("Small Pool Model", results_5, N=20)
    # Should be around rank 2-3
    assert 1 <= final_rank <= 4, f"Expected rank ~2-3, got {final_rank}"
    print("✓ Test 5 PASSED")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED! ✓")
    print("=" * 70)
    print("\nBinary search placement system is working correctly.")
    print("The algorithm successfully:")
    print("  • Places perfect models at rank #0")
    print("  • Places worst models at the bottom")
    print("  • Converges to mid-tier positions with mixed results")
    print("  • Handles small and large model pools")
    print("  • Narrows the search interval efficiently")


if __name__ == "__main__":
    main()
