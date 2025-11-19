#!/usr/bin/env python3
"""
Evaluate a new LLM model with a 10-game budget to determine its ELO ranking.

This script runs a series of games for a test model, starting at median ELO
and adaptively selecting opponents based on win/loss results. The model moves
up or down the ELO ladder after each game, allowing it to naturally settle
into its appropriate ranking position.

Usage:
    python backend/cli/evaluate_model.py --model <model_name> [--games 10]
"""

import os
import sys
import json
import argparse
import subprocess
from typing import List, Tuple, Dict, Optional
from pathlib import Path

# Add parent directory to path to import from main.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import run_simulation
from data_access.api_queries import get_model_by_name, get_all_models
from llm_providers import create_llm_provider


def load_current_rankings() -> List[Tuple[str, float]]:
    """
    Load current ELO rankings from stats_simple.json.
    
    Returns:
        List of tuples (model_name, elo) sorted by ELO descending.
    """
    stats_path = os.path.join(os.path.dirname(__file__), '..', 'completed_games', 'stats_simple.json')
    
    try:
        with open(stats_path, 'r') as f:
            stats = json.load(f)
    except FileNotFoundError:
        print(f"Warning: {stats_path} not found. Starting with empty rankings.")
        return []
    
    # Extract model -> ELO mappings and sort by ELO descending
    rankings = [(model, data['elo']) for model, data in stats.items()]
    rankings.sort(key=lambda x: x[1], reverse=True)
    
    return rankings


def get_median_elo(rankings: List[Tuple[str, float]]) -> float:
    """
    Calculate median ELO from current rankings.
    
    Args:
        rankings: List of (model_name, elo) tuples
        
    Returns:
        Median ELO value, or 1500 if no rankings exist
    """
    if not rankings:
        return 1500.0
    
    elos = [elo for _, elo in rankings]
    n = len(elos)
    
    if n % 2 == 0:
        return (elos[n // 2 - 1] + elos[n // 2]) / 2
    else:
        return elos[n // 2]


def test_model_response(model_config: Dict, skip_api_test: bool = False) -> bool:
    """
    Test if a model can respond to a simple query.
    
    Args:
        model_config: Configuration dictionary for the model
        skip_api_test: If True, skip actual API call (for testing)
        
    Returns:
        True if model responds successfully, False otherwise
    """
    if skip_api_test:
        return True  # Assume all models work in test mode
    
    try:
        provider = create_llm_provider(model_config)
        # Send a simple test query
        response = provider.get_response("Test: Reply with UP")
        # If we get any response without error, the model works
        return bool(response)
    except Exception as e:
        print(f"⚠️  Test failed: {str(e)[:80]}")
        return False


def get_current_test_model_elo(test_model: str, rankings: List[Tuple[str, float]]) -> Optional[float]:
    """
    Get the current ELO for the test model if it exists in rankings.
    
    Args:
        test_model: Name of the test model
        rankings: List of (model_name, elo) tuples
        
    Returns:
        Current ELO if model exists, None otherwise
    """
    for model, elo in rankings:
        if model == test_model:
            return elo
    return None


def calculate_jump_percentage(game_num: int, total_games: int = 10) -> float:
    """
    Calculate what percentage of the rankings to jump based on game number.

    Early games have high variance (exploration), later games refine position (exploitation).
    Uses percentages so it scales appropriately whether there are 20 or 100 models.
    Designed so that 5 consecutive wins lead to facing #1 by game 6.

    Args:
        game_num: Current game number (1-indexed)
        total_games: Total number of evaluation games

    Returns:
        Percentage of rankings to jump (0.0 to 1.0)
    """
    if game_num <= 2:
        return 0.10  # Early exploration - jump ~10% of rankings
    elif game_num <= 5:
        return 0.15  # Medium exploration - jump ~15% of rankings
    elif game_num <= 7:
        return 0.10  # Narrowing in - jump ~10% of rankings
    else:
        return 0.05  # Fine-tuning - jump ~5% of rankings


def select_next_opponent(
    test_model: str,
    current_elo: float,
    rankings: List[Tuple[str, float]],
    last_result: Optional[str],
    played_opponents: set,
    available_models: set,
    model_configs: Dict,
    game_num: int = 1,
    max_attempts: int = 5,
    skip_api_test: bool = False
) -> Tuple[str, float]:
    """
    Select the next opponent based on current ELO and last game result.
    Tests the selected model to ensure it can respond before returning.

    Strategy uses variance decay:
    - Early games (1-3): Make large jumps (7 positions) to quickly find skill level
    - Mid games (4-6): Make medium jumps (4 positions) to narrow in
    - Late games (7-10): Make small jumps (1 position) to fine-tune exact ELO
    - First game or tie: Find model closest to current ELO
    - After win: Find higher ELO opponent (with jump size)
    - After loss: Find lower ELO opponent (with jump size)
    - Prefer opponents not yet played
    - Test each candidate to ensure it works

    Args:
        test_model: Name of the model being evaluated
        current_elo: Current ELO of the test model
        rankings: List of (model_name, elo) tuples sorted descending
        last_result: 'won', 'lost', 'tied', or None for first game
        played_opponents: Set of model names already played against
        available_models: Set of model names that have valid configurations
        model_configs: Dictionary of all model configurations
        game_num: Current game number (1-indexed) for variance decay
        max_attempts: Maximum number of models to test before giving up

    Returns:
        Tuple of (opponent_name, opponent_elo)
    """
    # Filter out the test model itself and models without configs
    available_opponents = [(m, e) for m, e in rankings if m != test_model and m in available_models]
    
    if not available_opponents:
        raise ValueError("No opponents available!")
    
    # Separate into played and unplayed opponents
    unplayed = [(m, e) for m, e in available_opponents if m not in played_opponents]
    played = [(m, e) for m, e in available_opponents if m in played_opponents]

    # Prefer unplayed opponents, but fall back to played if necessary
    candidates = unplayed if unplayed else played

    # Calculate jump percentage based on game number (variance decay strategy)
    jump_percentage = calculate_jump_percentage(game_num)

    # Try multiple candidates until we find one that works
    for attempt in range(max_attempts):
        if last_result is None or last_result == 'tied':
            # First game or tie: find closest ELO match
            # Sort by distance to current ELO and pick the attempt-th closest
            sorted_candidates = sorted(candidates, key=lambda x: abs(x[1] - current_elo))
            if attempt >= len(sorted_candidates):
                break
            selected = sorted_candidates[attempt]

        elif last_result == 'won':
            # Won: find higher ELO opponent with variance-based jump
            higher_elo = sorted([(m, e) for m, e in candidates if e > current_elo], key=lambda x: x[1])
            if not higher_elo:
                # Already at top, use highest available
                higher_elo = sorted(candidates, key=lambda x: x[1], reverse=True)
            if attempt >= len(higher_elo):
                break
            # Jump ahead by percentage of available higher-ranked opponents, plus retry offset
            jump_positions = max(1, int(len(higher_elo) * jump_percentage))
            jump_index = min(jump_positions - 1 + attempt, len(higher_elo) - 1)
            selected = higher_elo[jump_index]

        else:  # last_result == 'lost'
            # Lost: find lower ELO opponent with variance-based jump
            lower_elo = sorted([(m, e) for m, e in candidates if e < current_elo], key=lambda x: x[1], reverse=True)
            if not lower_elo:
                # Already at bottom, use lowest available
                lower_elo = sorted(candidates, key=lambda x: x[1])
            if attempt >= len(lower_elo):
                break
            # Jump down by percentage of available lower-ranked opponents, plus retry offset
            jump_positions = max(1, int(len(lower_elo) * jump_percentage))
            jump_index = min(jump_positions - 1 + attempt, len(lower_elo) - 1)
            selected = lower_elo[jump_index]
        
        opponent_name, opponent_elo = selected
        
        # Test if this model can respond
        print(f"  Testing {opponent_name}...", end=" ")
        if test_model_response(model_configs[opponent_name], skip_api_test=skip_api_test):
            print("✓ Ready")
            return opponent_name, opponent_elo
        else:
            print(f"✗ Failed, trying next candidate...")
            # Remove from candidates to avoid re-testing
            candidates = [(m, e) for m, e in candidates if m != opponent_name]
            if not candidates:
                break
    
    # If we exhausted all attempts, return the last selected (even if untested)
    raise ValueError(f"Could not find a working opponent after {max_attempts} attempts!")


def run_game_and_update_stats(
    test_model_config: Dict,
    opponent_model_config: Dict,
    game_params: argparse.Namespace
) -> Dict:
    """
    Run a game between test model and opponent, then update all stats.
    
    Args:
        test_model_config: Configuration for the test model
        opponent_model_config: Configuration for the opponent model
        game_params: Game parameters (width, height, max_rounds, num_apples)
        
    Returns:
        Dictionary with game results including game_id, final_scores, game_result
    """
    # Run the simulation
    result = run_simulation(test_model_config, opponent_model_config, game_params)
    
    # Update all stats by re-running elo_tracker
    completed_games_dir = os.path.join(os.path.dirname(__file__), '..', 'completed_games')
    elo_tracker_path = os.path.join(os.path.dirname(__file__), '..', 'elo_tracker.py')
    
    print("  Recalculating ELO ratings...")
    subprocess.run(
        ['python', elo_tracker_path, completed_games_dir, '--output', completed_games_dir],
        capture_output=True,
        text=True
    )
    
    return result


def evaluate_model(
    model_name: str,
    num_games: int = 10,
    width: int = 10,
    height: int = 10,
    max_rounds: int = 100,
    num_apples: int = 5
):
    """
    Main orchestration function to evaluate a model over multiple games.
    
    Args:
        model_name: Name of the model to evaluate
        num_games: Number of games to play (default: 10)
        width: Board width (default: 10)
        height: Board height (default: 10)
        max_rounds: Maximum rounds per game (default: 100)
        num_apples: Number of apples on board (default: 5)
    """
    print("=" * 70)
    print(f"Starting {num_games}-Game Evaluation for: {model_name}")
    print("=" * 70)
    
    # Load model configuration from database
    test_model_config = get_model_by_name(model_name)

    if test_model_config is None:
        print(f"Error: Model '{model_name}' not found in database")
        all_models = get_all_models()
        available_model_names = [m['name'] for m in all_models]
        print(f"Available models: {', '.join(sorted(available_model_names))}")
        sys.exit(1)

    # Load all models to create available_models set and model_configs dict
    all_models = get_all_models()
    available_models = {m['name'] for m in all_models}
    model_configs = {m['name']: m for m in all_models}

    # Create game parameters object
    game_params = argparse.Namespace(
        width=width,
        height=height,
        max_rounds=max_rounds,
        num_apples=num_apples
    )
    
    # Load initial rankings
    rankings = load_current_rankings()
    
    if not rankings:
        print("Warning: No existing rankings found. This will be the first model.")
        sys.exit(1)
    
    # Check if test model already has an ELO
    initial_elo = get_current_test_model_elo(model_name, rankings)
    if initial_elo is not None:
        print(f"Model already has games played. Current ELO: {initial_elo:.2f}")
        print(f"Starting evaluation from current ELO...\n")
        current_elo = initial_elo
    else:
        median_elo = get_median_elo(rankings)
        print(f"Initial median ELO: {median_elo:.2f}")
        print(f"Model will start at median ELO and adapt based on results.\n")
        current_elo = median_elo
    
    # Track game results
    played_opponents = set()
    game_results = []
    wins = 0
    losses = 0
    ties = 0
    last_result = None
    
    # Play the evaluation games
    for game_num in range(1, num_games + 1):
        print(f"\n{'=' * 70}")
        print(f"Game {game_num}/{num_games}")
        print('=' * 70)
        
        # Select opponent (with pre-flight testing and variance decay)
        opponent_name, opponent_elo = select_next_opponent(
            model_name, current_elo, rankings, last_result, played_opponents, available_models, model_configs, game_num
        )
        opponent_config = model_configs[opponent_name]
        
        print(f"\n{model_name} (ELO: {current_elo:.2f}) vs {opponent_name} (ELO: {opponent_elo:.2f})")
        played_opponents.add(opponent_name)
        
        # Run game
        result = run_game_and_update_stats(test_model_config, opponent_config, game_params)
        
        # Determine result for test model (player 0)
        test_result = result['game_result']['0']
        opponent_result = result['game_result']['1']
        test_score = result['final_scores']['0']
        opponent_score = result['final_scores']['1']
        
        # Update win/loss/tie counts
        if test_result == 'won':
            wins += 1
            last_result = 'won'
        elif test_result == 'lost':
            losses += 1
            last_result = 'lost'
        else:
            ties += 1
            last_result = 'tied'
        
        # Reload rankings to get updated ELO
        rankings = load_current_rankings()
        new_elo = get_current_test_model_elo(model_name, rankings)
        
        if new_elo is None:
            print(f"Warning: Could not find updated ELO for {model_name}")
            new_elo = current_elo
        
        # Display result
        print(f"\nResult: {test_result.upper()} | Score: {test_score}-{opponent_score} | New ELO: {new_elo:.2f}")
        elo_change = new_elo - current_elo
        elo_symbol = "+" if elo_change >= 0 else ""
        print(f"ELO Change: {elo_symbol}{elo_change:.2f}")
        
        # Store game result
        game_results.append({
            'game_num': game_num,
            'opponent': opponent_name,
            'opponent_elo': opponent_elo,
            'result': test_result,
            'score': f"{test_score}-{opponent_score}",
            'elo_before': current_elo,
            'elo_after': new_elo
        })
        
        current_elo = new_elo
    
    # Print final summary
    print("\n" + "=" * 70)
    print("EVALUATION COMPLETE!")
    print("=" * 70)
    print(f"\nModel: {model_name}")
    print(f"Games Played: {num_games} | Wins: {wins} | Losses: {losses} | Ties: {ties}")
    
    if initial_elo:
        print(f"Starting ELO: {initial_elo:.2f}")
    else:
        print(f"Starting ELO: {get_median_elo(load_current_rankings()):.2f} (median)")
    
    print(f"Final ELO: {current_elo:.2f}")
    
    # Get final ranking
    final_rankings = load_current_rankings()
    rank = next((i + 1 for i, (m, _) in enumerate(final_rankings) if m == model_name), None)
    if rank:
        print(f"Final Rank: #{rank} of {len(final_rankings)} models")
    
    # Print game-by-game summary
    print("\n" + "-" * 70)
    print("Game-by-Game Summary:")
    print("-" * 70)
    for game in game_results:
        print(f"Game {game['game_num']}: vs {game['opponent']} (ELO: {game['opponent_elo']:.2f}) - "
              f"{game['result'].upper()} {game['score']} - "
              f"ELO: {game['elo_before']:.2f} → {game['elo_after']:.2f}")
    
    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate a new LLM model with a limited-game budget to determine its ELO ranking."
    )
    parser.add_argument(
        '--model',
        type=str,
        required=True,
        help="Model name from model_list.yaml to evaluate"
    )
    parser.add_argument(
        '--games',
        type=int,
        default=10,
        help="Number of evaluation games to play (default: 10)"
    )
    parser.add_argument(
        '--width',
        type=int,
        default=10,
        help="Board width (default: 10)"
    )
    parser.add_argument(
        '--height',
        type=int,
        default=10,
        help="Board height (default: 10)"
    )
    parser.add_argument(
        '--max_rounds',
        type=int,
        default=100,
        help="Maximum rounds per game (default: 100)"
    )
    parser.add_argument(
        '--num_apples',
        type=int,
        default=5,
        help="Number of apples on board (default: 5)"
    )
    
    args = parser.parse_args()
    
    evaluate_model(
        model_name=args.model,
        num_games=args.games,
        width=args.width,
        height=args.height,
        max_rounds=args.max_rounds,
        num_apples=args.num_apples
    )


if __name__ == "__main__":
    main()

