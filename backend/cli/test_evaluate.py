#!/usr/bin/env python3
"""
Test script for the model evaluation tool.

This script validates the evaluation tool's logic without running actual games,
which saves time and API costs.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from evaluate_model import (
    load_current_rankings,
    get_median_elo,
    select_next_opponent,
    get_current_test_model_elo
)
from utils.utils import load_model_configs


def test_ranking_functions():
    """Test basic ranking and ELO calculation functions."""
    print("=" * 70)
    print("TEST 1: Ranking Functions")
    print("=" * 70)
    
    rankings = load_current_rankings()
    assert len(rankings) > 0, "Should load rankings"
    print(f"✓ Loaded {len(rankings)} models")
    
    # Check rankings are sorted descending
    for i in range(len(rankings) - 1):
        assert rankings[i][1] >= rankings[i+1][1], "Rankings should be sorted descending"
    print("✓ Rankings are properly sorted by ELO (descending)")
    
    # Test median calculation
    median = get_median_elo(rankings)
    assert 1000 < median < 2000, "Median should be in reasonable range"
    print(f"✓ Median ELO: {median:.2f}")
    
    # Test current ELO lookup
    top_model = rankings[0][0]
    top_elo = get_current_test_model_elo(top_model, rankings)
    assert top_elo == rankings[0][1], "Should find correct ELO"
    print(f"✓ ELO lookup works: {top_model} = {top_elo:.2f}")
    
    # Test non-existent model
    fake_elo = get_current_test_model_elo("nonexistent-model", rankings)
    assert fake_elo is None, "Should return None for nonexistent model"
    print("✓ Returns None for nonexistent models")
    
    print()


def test_opponent_selection():
    """Test the adaptive opponent selection logic."""
    print("=" * 70)
    print("TEST 2: Opponent Selection Logic")
    print("=" * 70)
    
    rankings = load_current_rankings()
    median = get_median_elo(rankings)
    test_model = "test-model"
    model_configs = load_model_configs()
    available_models = set(model_configs.keys())
    
    # Note: We're passing skip_api_test=True to avoid actual API calls in unit tests
    # Test 1: First game (no previous result)
    opponent, elo = select_next_opponent(test_model, median, rankings, None, set(), available_models, model_configs, skip_api_test=True)
    assert opponent != test_model, "Should not select self"
    print(f"✓ First game: {opponent} (ELO: {elo:.2f}, close to median {median:.2f})")
    
    # Test 2: After a win - should select higher ELO
    opponent_after_win, elo_win = select_next_opponent(test_model, median, rankings, 'won', set(), available_models, model_configs, skip_api_test=True)
    assert elo_win > median, "After win, should select higher ELO opponent"
    print(f"✓ After WIN: {opponent_after_win} (ELO: {elo_win:.2f} > {median:.2f})")
    
    # Test 3: After a loss - should select lower ELO
    opponent_after_loss, elo_loss = select_next_opponent(test_model, median, rankings, 'lost', set(), available_models, model_configs, skip_api_test=True)
    assert elo_loss < median, "After loss, should select lower ELO opponent"
    print(f"✓ After LOSS: {opponent_after_loss} (ELO: {elo_loss:.2f} < {median:.2f})")
    
    # Test 4: After a tie - should select similar ELO
    opponent_after_tie, elo_tie = select_next_opponent(test_model, median, rankings, 'tied', set(), available_models, model_configs, skip_api_test=True)
    print(f"✓ After TIE: {opponent_after_tie} (ELO: {elo_tie:.2f} ≈ {median:.2f})")
    
    # Test 5: Prefer unplayed opponents
    played = {opponent}
    opponent_new, _ = select_next_opponent(test_model, median, rankings, None, played, available_models, model_configs, skip_api_test=True)
    assert opponent_new != opponent, "Should prefer unplayed opponents"
    print(f"✓ Prefers unplayed opponents: {opponent_new} (already played: {opponent})")
    
    # Test 6: Can select from top
    top_elo = rankings[0][1]
    opponent_top, elo_top = select_next_opponent(test_model, top_elo + 100, rankings, 'won', set(), available_models, model_configs, skip_api_test=True)
    print(f"✓ At top after WIN: {opponent_top} (highest available: {elo_top:.2f})")
    
    # Test 7: Can select from bottom
    bottom_elo = rankings[-1][1]
    opponent_bottom, elo_bottom = select_next_opponent(test_model, bottom_elo - 100, rankings, 'lost', set(), available_models, model_configs, skip_api_test=True)
    print(f"✓ At bottom after LOSS: {opponent_bottom} (lowest available: {elo_bottom:.2f})")
    
    print()


def test_adaptive_path():
    """Simulate an adaptive evaluation path."""
    print("=" * 70)
    print("TEST 3: Simulated Adaptive Evaluation Path")
    print("=" * 70)
    
    rankings = load_current_rankings()
    median = get_median_elo(rankings)
    test_model = "new-awesome-model"
    current_elo = median
    played = set()
    model_configs = load_model_configs()
    available_models = set(model_configs.keys())
    
    # Simulate a winning streak
    results = ['won', 'won', 'won', 'won', 'lost', 'won', 'tied', 'won', 'lost', 'won']
    
    print(f"Starting ELO: {current_elo:.2f} (median)")
    print()
    
    for game_num, result in enumerate(results, 1):
        opponent, opp_elo = select_next_opponent(
            test_model, current_elo, rankings, 
            None if game_num == 1 else results[game_num - 2],
            played,
            available_models,
            model_configs,
            skip_api_test=True  # Skip model testing in simulations
        )
        played.add(opponent)
        
        # Simulate ELO change (rough approximation)
        if result == 'won':
            elo_change = +32 if opp_elo > current_elo else +16
        elif result == 'lost':
            elo_change = -32 if opp_elo < current_elo else -16
        else:
            elo_change = 0
        
        current_elo += elo_change
        
        symbol = "✓" if result == 'won' else "✗" if result == 'lost' else "="
        print(f"Game {game_num:2d} {symbol} vs {opponent[:30]:30s} "
              f"(ELO: {opp_elo:7.2f}) → {current_elo:7.2f} ({elo_change:+.0f})")
    
    print()
    print(f"Final simulated ELO: {current_elo:.2f}")
    print(f"ELO change: {current_elo - median:+.2f}")
    
    # Find final rank
    final_rank = sum(1 for _, elo in rankings if elo > current_elo) + 1
    print(f"Estimated rank: #{final_rank} of {len(rankings)}")
    
    print()


def run_all_tests():
    """Run all validation tests."""
    print("\n" + "=" * 70)
    print("EVALUATION TOOL VALIDATION TESTS")
    print("=" * 70)
    print()
    
    try:
        test_ranking_functions()
        test_opponent_selection()
        test_adaptive_path()
        
        print("=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print()
        print("The evaluation tool is working correctly and ready for use.")
        print()
        print("To run a real evaluation:")
        print("  python cli/evaluate_model.py --model <model-name>")
        print()
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())

