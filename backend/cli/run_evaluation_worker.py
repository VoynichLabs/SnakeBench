#!/usr/bin/env python3
"""
Evaluation worker that processes queued models.

This worker pulls models from the evaluation queue and runs the configured
number of games against adaptive opponents using the database-backed system.

Unlike the standalone evaluate_model.py which uses file-based stats, this
worker is fully database-driven and integrates with the sync/queue system.

Usage:
    python backend/cli/run_evaluation_worker.py [--continuous] [--interval 60]
    python backend/cli/run_evaluation_worker.py --model "model-name"
"""

import os
import sys
import json
import time
import argparse
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

# Add parent directory to path to import from main.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import run_simulation
from database_postgres import get_connection
from llm_providers import create_llm_provider
from data_access import (
    get_next_queued_model,
    update_queue_status,
    decrement_attempts,
    get_queue_stats,
    enqueue_model,
    get_queued_model_by_id
)

# Add parent services directory to path for webhook service
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))
from webhook_service import send_evaluation_complete_webhook


def queue_model_by_name(model_name: str, attempts: int = 10) -> Optional[int]:
    """
    Lookup a model by name and queue it for evaluation.

    Args:
        model_name: Name of the model to queue
        attempts: Number of evaluation games to run (default: 10)

    Returns:
        Model ID if found and queued, None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, name
            FROM models
            WHERE name = %s
        """, (model_name,))

        row = cursor.fetchone()

        if not row:
            print(f"✗ Model '{model_name}' not found in database")
            return None

        model_id = row['id']
        print(f"✓ Found model: {row['name']} (ID: {model_id})")

        # Queue the model
        enqueue_model(model_id=model_id, attempts=attempts)
        print(f"✓ Queued model for {attempts} evaluation games")

        return model_id

    finally:
        conn.close()


def get_model_config_from_db(model_id: int) -> Optional[Dict[str, Any]]:
    """
    Build a model configuration dictionary from database data.

    Args:
        model_id: ID of the model

    Returns:
        Configuration dictionary compatible with run_simulation, or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                name,
                provider,
                model_slug,
                max_completion_tokens,
                metadata_json,
                pricing_input,
                pricing_output
            FROM models
            WHERE id = %s
        """, (model_id,))

        row = cursor.fetchone()

        if not row:
            return None

        name = row['name']
        provider = row['provider']
        model_slug = row['model_slug']
        max_tokens = row['max_completion_tokens']
        metadata_json = row['metadata_json']
        pricing_input = row['pricing_input']
        pricing_output = row['pricing_output']

        # Parse metadata if available
        metadata = {}
        if metadata_json:
            # PostgreSQL JSONB returns dict directly, SQLite returns string
            if isinstance(metadata_json, str):
                try:
                    metadata = json.loads(metadata_json)
                except json.JSONDecodeError:
                    pass
            elif isinstance(metadata_json, dict):
                metadata = metadata_json

        # Build config dictionary
        # Cap max_tokens to reasonable value to leave room for input tokens
        # Use model's max_completion_tokens if available, but cap at 16000
        # to ensure there's room for the game state in the prompt
        if max_tokens:
            # Use the smaller of: model's max or 16000
            capped_max_tokens = min(max_tokens, 16000)
        else:
            capped_max_tokens = 500

        config = {
            'name': name,
            'provider': provider,
            'model_name': model_slug,
            'max_tokens': capped_max_tokens,
        }

        # Add pricing information if available
        if pricing_input is not None and pricing_output is not None:
            config['pricing'] = {
                'input': pricing_input,
                'output': pricing_output
            }

        # Add any additional kwargs from metadata
        if 'kwargs' in metadata:
            config.update(metadata['kwargs'])

        return config

    finally:
        conn.close()


def get_current_elo(model_id: int) -> float:
    """
    Get the current ELO rating for a model.

    Args:
        model_id: ID of the model

    Returns:
        Current ELO rating
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT elo_rating
            FROM models
            WHERE id = %s
        """, (model_id,))

        row = cursor.fetchone()
        return row['elo_rating'] if row else 1500.0

    finally:
        conn.close()


def get_median_elo() -> float:
    """
    Calculate median ELO from all ranked models.

    Returns:
        Median ELO value, or 1500 if no ranked models exist
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT elo_rating
            FROM models
            WHERE test_status = 'ranked'
            ORDER BY elo_rating DESC
        """)

        elos = [row['elo_rating'] for row in cursor.fetchall()]

        if not elos:
            return 1500.0

        n = len(elos)
        if n % 2 == 0:
            return (elos[n // 2 - 1] + elos[n // 2]) / 2
        else:
            return elos[n // 2]

    finally:
        conn.close()


def get_ranked_models() -> List[Tuple[int, str, float]]:
    """
    Get list of all ranked models sorted by ELO.

    Returns:
        List of tuples (model_id, name, elo) sorted by ELO descending
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

        return [(row['id'], row['name'], row['elo_rating']) for row in cursor.fetchall()]

    finally:
        conn.close()


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
    test_model_id: int,
    current_elo: float,
    last_result: Optional[str],
    played_opponents: set,
    game_num: int = 1
) -> Optional[Tuple[int, str, float]]:
    """
    Select the next opponent based on current ELO and last game result.

    Strategy uses variance decay:
    - Early games (1-3): Make large jumps (7 positions) to quickly find skill level
    - Mid games (4-6): Make medium jumps (4 positions) to narrow in
    - Late games (7-10): Make small jumps (1 position) to fine-tune exact ELO
    - First game or tie: Find model closest to current ELO
    - After win: Find higher ELO opponent (with jump size)
    - After loss: Find lower ELO opponent (with jump size)
    - Prefer opponents not yet played

    Args:
        test_model_id: ID of the model being evaluated
        current_elo: Current ELO of the test model
        last_result: 'won', 'lost', 'tied', or None for first game
        played_opponents: Set of model IDs already played against
        game_num: Current game number (1-indexed) for variance decay

    Returns:
        Tuple of (opponent_id, opponent_name, opponent_elo) or None if no opponents
    """
    ranked = get_ranked_models()

    if not ranked:
        print("  ⚠️  No ranked models available for matchmaking")
        return None

    # Filter out the test model itself
    candidates = [(mid, name, elo) for mid, name, elo in ranked if mid != test_model_id]

    if not candidates:
        return None

    # Separate into played and unplayed opponents
    unplayed = [(mid, name, elo) for mid, name, elo in candidates if mid not in played_opponents]
    played = [(mid, name, elo) for mid, name, elo in candidates if mid in played_opponents]

    # Prefer unplayed opponents, but fall back to played if necessary
    pool = unplayed if unplayed else played

    # Calculate jump percentage based on game number (variance decay strategy)
    jump_percentage = calculate_jump_percentage(game_num)

    if last_result is None or last_result == 'tied':
        # First game or tie: find closest ELO match
        sorted_pool = sorted(pool, key=lambda x: abs(x[2] - current_elo))
        return sorted_pool[0] if sorted_pool else None

    elif last_result == 'won':
        # Won: find higher ELO opponent with variance-based jump
        higher_elo = sorted([(mid, name, elo) for mid, name, elo in pool if elo > current_elo],
                           key=lambda x: x[2])
        if higher_elo:
            # Jump ahead by percentage of available higher-ranked opponents
            jump_positions = max(1, int(len(higher_elo) * jump_percentage))
            jump_index = min(jump_positions - 1, len(higher_elo) - 1)
            return higher_elo[jump_index]
        # Already at top, use highest available
        return sorted(pool, key=lambda x: x[2], reverse=True)[0]

    else:  # last_result == 'lost'
        # Lost: find lower ELO opponent with variance-based jump
        lower_elo = sorted([(mid, name, elo) for mid, name, elo in pool if elo < current_elo],
                          key=lambda x: x[2], reverse=True)
        if lower_elo:
            # Jump down by percentage of available lower-ranked opponents
            jump_positions = max(1, int(len(lower_elo) * jump_percentage))
            jump_index = min(jump_positions - 1, len(lower_elo) - 1)
            return lower_elo[jump_index]
        # Already at bottom, use lowest available
        return sorted(pool, key=lambda x: x[2])[0]


def run_evaluation_game(
    test_model_id: int,
    test_model_config: Dict[str, Any],
    opponent_id: int,
    opponent_config: Dict[str, Any],
    game_params: argparse.Namespace
) -> Dict[str, Any]:
    """
    Run a single evaluation game between test model and opponent.

    The game is automatically persisted to the database by main.py's event-driven
    persistence, so we just need to run the simulation.

    Args:
        test_model_id: ID of test model
        test_model_config: Configuration for test model
        opponent_id: ID of opponent model
        opponent_config: Configuration for opponent model
        game_params: Game parameters

    Returns:
        Game result dictionary
    """
    print(f"  Running game: {test_model_config['name']} vs {opponent_config['name']}...")

    result = run_simulation(test_model_config, opponent_config, game_params)

    # Result includes game_id, final_scores, game_result
    # Database persistence happens automatically in main.py
    return result


def evaluate_queued_model(
    queue_entry: Dict[str, Any],
    game_params: argparse.Namespace
) -> bool:
    """
    Run evaluation games for a queued model.

    Args:
        queue_entry: Queue entry with model info
        game_params: Game parameters

    Returns:
        True if evaluation completed successfully, False otherwise
    """
    queue_id = queue_entry['queue_id']
    model_id = queue_entry['model_id']
    model_name = queue_entry['name']
    attempts_remaining = queue_entry['attempts_remaining']

    print(f"\n{'=' * 70}")
    print(f"Evaluating Model: {model_name}")
    print(f"Attempts remaining: {attempts_remaining}")
    print(f"{'=' * 70}")

    # Mark as running
    update_queue_status(queue_id, 'running')

    # Get model config
    test_model_config = get_model_config_from_db(model_id)

    if not test_model_config:
        print(f"✗ Could not load configuration for model {model_name}")
        update_queue_status(queue_id, 'failed', 'Could not load model configuration')
        return False

    # Perform health check to verify model is available on OpenRouter
    print(f"Checking if model is available on OpenRouter...")
    try:
        provider = create_llm_provider(test_model_config)
        if not provider.health_check():
            print(f"✗ Model {model_name} not found on OpenRouter (404)")
            update_queue_status(queue_id, 'failed', 'Model not found on OpenRouter (404)')
            return False
        print(f"✓ Model is available")
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        update_queue_status(queue_id, 'failed', f'Health check failed: {str(e)[:200]}')
        return False

    # Track game results
    played_opponents = set()
    current_elo = get_current_elo(model_id)
    last_result = None
    wins = 0
    losses = 0
    ties = 0

    # If this is a fresh model, start at median ELO
    if current_elo == 1500.0:
        median = get_median_elo()
        print(f"Starting ELO: {median:.2f} (median)")
        current_elo = median

    # Run evaluation games
    for game_num in range(1, attempts_remaining + 1):
        print(f"\n--- Game {game_num}/{attempts_remaining} ---")

        # Select opponent (with variance decay based on game number)
        opponent_info = select_next_opponent(model_id, current_elo, last_result, played_opponents, game_num)

        if not opponent_info:
            print("✗ No suitable opponents available")
            update_queue_status(queue_id, 'failed', 'No suitable opponents available')
            return False

        opponent_id, opponent_name, opponent_elo = opponent_info
        played_opponents.add(opponent_id)

        print(f"{model_name} (ELO: {current_elo:.2f}) vs {opponent_name} (ELO: {opponent_elo:.2f})")

        # Get opponent config
        opponent_config = get_model_config_from_db(opponent_id)

        if not opponent_config:
            print(f"✗ Could not load configuration for opponent {opponent_name}")
            continue

        try:
            # Run the game
            result = run_evaluation_game(
                model_id, test_model_config,
                opponent_id, opponent_config,
                game_params
            )

            # Parse result
            test_result = result['game_result']['0']
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

            # Get updated ELO (database was updated by main.py)
            new_elo = get_current_elo(model_id)
            elo_change = new_elo - current_elo

            print(f"Result: {test_result.upper()} | Score: {test_score}-{opponent_score}")
            print(f"ELO: {current_elo:.2f} → {new_elo:.2f} ({elo_change:+.2f})")

            current_elo = new_elo

            # Decrement attempts
            decrement_attempts(queue_id)

        except Exception as e:
            print(f"✗ Error running game: {e}")
            import traceback
            traceback.print_exc()
            # Continue with next game

    # Mark model as ranked and activate it
    print(f"Marking model {model_name} (ID: {model_id}) as ranked and active...")
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE models
            SET test_status = 'ranked', is_active = TRUE
            WHERE id = %s
        """, (model_id,))

        affected_rows = cursor.rowcount
        conn.commit()
        print(f"✓ Updated model status (affected rows: {affected_rows})")

    except Exception as e:
        print(f"✗ Error updating model status: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

    # Mark queue entry as done
    update_queue_status(queue_id, 'done')

    # Get total cost for this model's evaluation
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COALESCE(SUM(gp.cost), 0) as total_cost
        FROM game_participants gp
        JOIN models m ON gp.model_id = m.id
        WHERE m.id = %s
    """, (model_id,))
    result = cursor.fetchone()
    evaluation_cost = result['total_cost'] if result else 0.0
    conn.close()

    # Print summary
    print(f"\n{'=' * 70}")
    print(f"Evaluation Complete: {model_name}")
    print(f"{'=' * 70}")
    print(f"Games: {attempts_remaining} | Wins: {wins} | Losses: {losses} | Ties: {ties}")
    print(f"Final ELO: {current_elo:.2f}")
    print(f"Total Cost: ${evaluation_cost:.4f}")
    print(f"Status: Ranked")
    print(f"{'=' * 70}\n")

    # Send webhook notification
    send_evaluation_complete_webhook(
        model_name=model_name,
        final_elo=current_elo,
        games_played=attempts_remaining,
        wins=wins,
        losses=losses,
        ties=ties,
        total_cost=evaluation_cost
    )

    return True


def run_worker(
    continuous: bool = False,
    interval: int = 60,
    game_params: Optional[argparse.Namespace] = None,
    target_model_id: Optional[int] = None
):
    """
    Main worker loop to process evaluation queue.

    Args:
        continuous: If True, keep running and check for new jobs
        interval: Seconds to wait between checks in continuous mode
        game_params: Game parameters (width, height, rounds, apples)
        target_model_id: If specified, only process this specific model (one-off mode)
    """
    if game_params is None:
        game_params = argparse.Namespace(
            width=10,
            height=10,
            max_rounds=100,
            num_apples=5
        )

    print("=" * 70)
    print("Evaluation Worker Started")
    print("=" * 70)
    print(f"Mode: {'Continuous' if continuous else 'Single run'}")
    if continuous:
        print(f"Check interval: {interval}s")
    print("=" * 70)

    processed = 0

    while True:
        # If target_model_id is specified, only process that model
        if target_model_id is not None:
            queue_entry = get_queued_model_by_id(target_model_id)
            if queue_entry is None:
                print(f"✗ Model ID {target_model_id} not found in queue or not ready for evaluation")
                break
        else:
            # Check queue stats
            stats = get_queue_stats()
            queued_count = stats.get('queued', 0)

            if queued_count == 0:
                if processed > 0:
                    print(f"\n✓ Processed {processed} model(s), queue is now empty")

                if not continuous:
                    print("No more models in queue, exiting...")
                    break
                else:
                    print(f"Queue empty, waiting {interval}s for new jobs...")
                    time.sleep(interval)
                    continue

            # Get next model
            queue_entry = get_next_queued_model()

            if queue_entry is None:
                if not continuous:
                    break
                time.sleep(interval)
                continue

        # Evaluate the model
        try:
            success = evaluate_queued_model(queue_entry, game_params)
            if success:
                processed += 1
        except Exception as e:
            print(f"✗ Error evaluating model: {e}")
            import traceback
            traceback.print_exc()

            # Mark as failed
            update_queue_status(
                queue_entry['queue_id'],
                'failed',
                str(e)[:500]  # Truncate error message
            )

        # If we're targeting a specific model, exit after processing it
        if target_model_id is not None:
            break

        if not continuous:
            break

    print("\n" + "=" * 70)
    print(f"Worker finished. Total processed: {processed}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluation worker to process queued models"
    )
    parser.add_argument(
        '--model',
        type=str,
        help="Queue and evaluate a specific model by name (one-off evaluation)"
    )
    parser.add_argument(
        '--continuous',
        action='store_true',
        help="Run continuously, checking for new jobs at regular intervals"
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help="Seconds to wait between checks in continuous mode (default: 60)"
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
        '--max-rounds',
        type=int,
        default=100,
        help="Maximum rounds per game (default: 100)"
    )
    parser.add_argument(
        '--num-apples',
        type=int,
        default=5,
        help="Number of apples on board (default: 5)"
    )

    args = parser.parse_args()

    game_params = argparse.Namespace(
        width=args.width,
        height=args.height,
        max_rounds=args.max_rounds,
        num_apples=args.num_apples
    )

    # If --model is specified, queue that specific model and run single evaluation
    target_model_id = None
    if args.model:
        print(f"One-off evaluation mode for model: {args.model}")
        target_model_id = queue_model_by_name(args.model)
        if target_model_id is None:
            print("\nAvailable models:")
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM models ORDER BY name LIMIT 20")
            for row in cursor.fetchall():
                print(f"  - {row['name']}")
            conn.close()
            sys.exit(1)
        print()

    run_worker(
        continuous=args.continuous,
        interval=args.interval,
        game_params=game_params,
        target_model_id=target_model_id
    )


if __name__ == "__main__":
    main()
