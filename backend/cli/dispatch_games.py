#!/usr/bin/env python3
"""
Mass-parallel game dispatcher using Celery task queue.

This CLI submits multiple game tasks to the Celery queue for parallel execution
by worker processes. It only orchestrates; actual game execution happens inside workers.

Usage:
    # Dispatch 50 games between two models
    python backend/cli/dispatch_games.py --model_a "gpt-4" --model_b "claude-3" --count 50

    # Dispatch with custom game parameters
    python backend/cli/dispatch_games.py --model_a "gpt-4" --model_b "claude-3" --count 10 \
        --width 15 --height 15 --max_rounds 150

    # Monitor task status
    python backend/cli/dispatch_games.py --monitor <task_group_id>
"""

import os
import sys
import time
import argparse
import uuid
from typing import List, Dict, Any, Optional
from celery.result import AsyncResult, GroupResult

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tasks import run_game_task
from data_access.api_queries import get_model_by_name


def dispatch_games(
    model_name_a: str,
    model_name_b: str,
    count: int,
    game_params: Dict[str, Any],
    monitor: bool = False
) -> str:
    """
    Dispatch multiple game tasks to the Celery queue.

    Args:
        model_name_a: Name of first model
        model_name_b: Name of second model
        count: Number of games to dispatch
        game_params: Game configuration (width, height, rounds, apples)
        monitor: If True, wait and monitor task completion

    Returns:
        Group ID for tracking this batch of tasks
    """
    print("=" * 70)
    print(f"Dispatching {count} games: {model_name_a} vs {model_name_b}")
    print("=" * 70)

    # Get model configurations from database
    print(f"\nLoading model configurations...")
    config_a = get_model_by_name(model_name_a)
    config_b = get_model_by_name(model_name_b)

    if config_a is None:
        print(f"✗ Model '{model_name_a}' not found in database")
        sys.exit(1)
    if config_b is None:
        print(f"✗ Model '{model_name_b}' not found in database")
        sys.exit(1)

    print(f"✓ Loaded: {config_a['name']}")
    print(f"✓ Loaded: {config_b['name']}")

    # Create task group
    group_id = str(uuid.uuid4())
    print(f"\nBatch ID: {group_id}")

    # Submit tasks to queue
    print(f"\nSubmitting {count} tasks to queue...")
    task_ids = []

    for i in range(count):
        result = run_game_task.apply_async(
            args=[config_a, config_b, game_params],
            task_id=f"{group_id}-game-{i}",
        )
        task_ids.append(result.id)

        # Progress indicator
        if (i + 1) % 10 == 0 or (i + 1) == count:
            print(f"  Queued: {i + 1}/{count} tasks")

    print(f"\n✓ All {count} tasks submitted to queue")
    print(f"✓ Workers will process tasks in parallel")

    # Monitor if requested
    if monitor:
        print("\n" + "=" * 70)
        print("MONITORING TASK EXECUTION")
        print("=" * 70)
        monitor_tasks(task_ids)
    else:
        print("\nAdd --monitor flag to watch task execution in real-time")

    return group_id


def monitor_tasks(task_ids: List[str]):
    """
    Monitor the status of submitted tasks until completion.

    Args:
        task_ids: List of Celery task IDs to monitor
    """
    print("\nMonitoring task progress (Ctrl+C to stop monitoring)...\n")

    try:
        while True:
            # Check status of all tasks
            results = [AsyncResult(task_id) for task_id in task_ids]

            pending = sum(1 for r in results if r.state == 'PENDING')
            started = sum(1 for r in results if r.state == 'STARTED')
            success = sum(1 for r in results if r.state == 'SUCCESS')
            failed = sum(1 for r in results if r.state == 'FAILURE')
            retry = sum(1 for r in results if r.state == 'RETRY')

            total = len(task_ids)
            completed = success + failed
            in_progress = started + retry

            # Progress bar
            progress = completed / total if total > 0 else 0
            bar_width = 40
            filled = int(bar_width * progress)
            bar = '█' * filled + '░' * (bar_width - filled)

            # Status line
            print(f"\r[{bar}] {completed}/{total} complete "
                  f"| ✓ {success} | ✗ {failed} | ⟳ {retry} | ▶ {in_progress} | ⋯ {pending}",
                  end='', flush=True)

            # Check if all done
            if completed == total:
                print("\n\n✓ All tasks completed!")

                if failed > 0:
                    print(f"\n⚠ {failed} task(s) failed. Check worker logs for details.")
                    print("\nFailed task IDs:")
                    for r in results:
                        if r.state == 'FAILURE':
                            print(f"  - {r.id}")
                            try:
                                print(f"    Error: {r.info}")
                            except:
                                pass

                break

            time.sleep(2)  # Update every 2 seconds

    except KeyboardInterrupt:
        print("\n\n⚠ Monitoring stopped (tasks continue running in background)")
        print(f"Tasks will complete independently on workers")


def get_batch_status(batch_id: str):
    """
    Display status of a previously submitted batch.

    Args:
        batch_id: Batch ID from dispatch_games()
    """
    batch_file = f"batch_{batch_id}.txt"

    if not os.path.exists(batch_file):
        print(f"✗ Batch file not found: {batch_file}")
        sys.exit(1)

    # Load task IDs from batch file
    task_ids = []
    with open(batch_file, 'r') as f:
        lines = f.readlines()
        # Skip header lines, then read task IDs
        in_task_section = False
        for line in lines:
            if line.strip() == "Task IDs:":
                in_task_section = True
                continue
            if in_task_section and line.strip():
                task_ids.append(line.strip())

    print(f"Loaded {len(task_ids)} tasks from batch {batch_id}")
    monitor_tasks(task_ids)


def main():
    parser = argparse.ArgumentParser(
        description="Dispatch multiple games to Celery queue for parallel execution"
    )

    # Dispatch mode arguments
    parser.add_argument('--model_a', type=str, help="Name of first model")
    parser.add_argument('--model_b', type=str, help="Name of second model")
    parser.add_argument('--count', type=int, default=1,
                       help="Number of games to dispatch (default: 1)")
    parser.add_argument('--monitor', type=str, nargs='?', const=True,
                       help="Monitor task execution (optionally provide batch ID)")

    # Game parameters
    parser.add_argument('--width', type=int, default=10, help="Board width (default: 10)")
    parser.add_argument('--height', type=int, default=10, help="Board height (default: 10)")
    parser.add_argument('--max_rounds', type=int, default=100,
                       help="Maximum rounds per game (default: 100)")
    parser.add_argument('--num_apples', type=int, default=5,
                       help="Number of apples on board (default: 5)")

    args = parser.parse_args()

    # Monitor-only mode
    if args.monitor and args.monitor is not True:
        get_batch_status(args.monitor)
        return

    # Dispatch mode - require model arguments
    if not args.model_a or not args.model_b:
        parser.error("--model_a and --model_b are required for dispatching games")

    game_params = {
        'width': args.width,
        'height': args.height,
        'max_rounds': args.max_rounds,
        'num_apples': args.num_apples,
    }

    dispatch_games(
        model_name_a=args.model_a,
        model_name_b=args.model_b,
        count=args.count,
        game_params=game_params,
        monitor=bool(args.monitor)
    )


if __name__ == "__main__":
    main()
