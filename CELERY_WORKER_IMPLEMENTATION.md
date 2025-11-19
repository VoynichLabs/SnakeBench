# Celery Worker Implementation Checklist

## Overview
Implement a distributed task queue system using Celery and Redis to enable parallel game execution. This is **fully backwards compatible** - all existing scripts continue to work unchanged.

### Architecture
```
dispatch_games.py → Redis (Queue) → Celery Workers → Database
   (Producer)         (Broker)       (Consumers)      (Storage)
```

---

## 📋 Implementation Checklist

### Phase 1: Dependencies & Core Infrastructure

- [x] **1.1 Update Dependencies**
  - File: `backend/requirements.txt`
  - Add these lines to the end:
    ```txt
    celery[redis]==5.4.0
    redis==5.2.1
    ```
  - Run: `pip install -r backend/requirements.txt`

---

- [x] **1.2 Create Celery Application**
  - Create file: `backend/celery_app.py`
  - Copy the Celery app configuration code (see reference below)
  - Configures Redis connection and task routing

<details>
<summary>📄 Code for backend/celery_app.py</summary>

```python
"""
Celery application for distributed game execution.

This module initializes Celery with Redis as the broker and result backend.
Workers connect to this app to pull and execute game tasks.
"""
import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Redis connection URL from environment
# Format: redis://[user:password@]hostname:port/db_number
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Initialize Celery app
app = Celery(
    'snakebench',
    broker=REDIS_URL,
    backend=REDIS_URL,
)

# Celery configuration
app.conf.update(
    # Task execution settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # Task result settings
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,  # Store additional task metadata

    # Worker settings
    worker_prefetch_multiplier=1,  # Workers fetch one task at a time
    task_acks_late=True,  # Acknowledge task after completion (improves reliability)
    task_reject_on_worker_lost=True,  # Re-queue task if worker dies

    # Task routing
    task_routes={
        'backend.tasks.run_game_task': {'queue': 'games'},
    },

    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

if __name__ == '__main__':
    app.start()
```
</details>

---

- [x] **1.3 Create Game Execution Task**
  - Create file: `backend/tasks.py`
  - Copy the task wrapper code (see reference below)
  - Wraps existing `run_simulation()` as a Celery task with retry logic

<details>
<summary>📄 Code for backend/tasks.py</summary>

```python
"""
Celery tasks for game execution.

This module defines distributed tasks that can be executed by Celery workers.
Each task wraps existing game logic from main.py.
"""
import argparse
from typing import Dict, Any
from celery import Task
from celery.utils.log import get_task_logger

from celery_app import app
from main import run_simulation

logger = get_task_logger(__name__)


class GameTask(Task):
    """
    Base task with retry logic and error handling.
    """
    autoretry_for = (Exception,)  # Retry on any exception
    retry_kwargs = {'max_retries': 3, 'countdown': 5}  # Retry up to 3 times, wait 5s between
    retry_backoff = True  # Exponential backoff (5s, 10s, 20s)
    retry_jitter = True  # Add randomness to prevent thundering herd


@app.task(base=GameTask, bind=True, name='backend.tasks.run_game_task')
def run_game_task(
    self,
    model_config_1: Dict[str, Any],
    model_config_2: Dict[str, Any],
    game_params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute a single snake game between two models.

    This task wraps main.py's run_simulation() function to make it executable
    by Celery workers. The game result is automatically persisted to the database
    by the existing event-driven system in main.py.

    Args:
        model_config_1: Configuration dictionary for player 1 (from database)
        model_config_2: Configuration dictionary for player 2 (from database)
        game_params: Game parameters (width, height, max_rounds, num_apples)

    Returns:
        Dictionary with game results:
        {
            'game_id': str,
            'final_scores': Dict[str, int],
            'game_result': Dict[str, str],  # 'won', 'lost', or 'tied' for each player
            'task_id': str  # Celery task ID for tracking
        }

    Raises:
        Exception: If game execution fails after retries
    """
    logger.info(
        f"Starting game {self.request.id}: "
        f"{model_config_1['name']} vs {model_config_2['name']}"
    )

    # Convert game_params dict to argparse.Namespace (expected by run_simulation)
    params = argparse.Namespace(**game_params)

    try:
        # Run the simulation using existing logic
        # This automatically handles database persistence
        result = run_simulation(model_config_1, model_config_2, params)

        # Add task ID for tracking
        result['task_id'] = self.request.id

        logger.info(
            f"Game {result['game_id']} complete: "
            f"Score {result['final_scores']['0']}-{result['final_scores']['1']}, "
            f"Result: {result['game_result']}"
        )

        return result

    except Exception as e:
        logger.error(
            f"Game execution failed (attempt {self.request.retries + 1}/3): {e}",
            exc_info=True
        )
        raise  # Re-raise to trigger retry logic


@app.task(name='backend.tasks.health_check')
def health_check() -> Dict[str, str]:
    """
    Simple health check task for monitoring worker status.

    Returns:
        Dict with status message
    """
    return {'status': 'healthy', 'message': 'Worker is operational'}
```
</details>

---

### Phase 2: Orchestration CLI

- [x] **2.1 Create Dispatch CLI**
  - Create file: `backend/cli/dispatch_games.py`
  - Copy the dispatcher code (see reference below)
  - Provides CLI for submitting games to the queue
  - Make executable: `chmod +x backend/cli/dispatch_games.py`

<details>
<summary>📄 Code for backend/cli/dispatch_games.py</summary>

```python
#!/usr/bin/env python3
"""
Mass-parallel game dispatcher using Celery task queue.

This CLI submits multiple game tasks to the Celery queue for parallel execution
by worker processes. Unlike the standalone evaluate_model.py, this dispatcher
does not execute games directly - it orchestrates them.

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

    # Save batch metadata
    batch_file = f"batch_{group_id}.txt"
    with open(batch_file, 'w') as f:
        f.write(f"Batch ID: {group_id}\n")
        f.write(f"Model A: {model_name_a}\n")
        f.write(f"Model B: {model_name_b}\n")
        f.write(f"Games: {count}\n")
        f.write(f"Game Params: {game_params}\n")
        f.write(f"\nTask IDs:\n")
        for task_id in task_ids:
            f.write(f"{task_id}\n")

    print(f"\nBatch info saved to: {batch_file}")

    # Monitor if requested
    if monitor:
        print("\n" + "=" * 70)
        print("MONITORING TASK EXECUTION")
        print("=" * 70)
        monitor_tasks(task_ids)
    else:
        print("\nUse --monitor to watch task execution in real-time")
        print(f"Or run: python backend/cli/dispatch_games.py --monitor {group_id}")

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
    parser.add_argument('--count', type=int, default=10,
                       help="Number of games to dispatch (default: 10)")
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
```
</details>

---

### Phase 3: Worker Deployment Configuration

- [x] **3.1 Create Railway Worker Config**
  - Create file: `worker.celery.railway.json` (in project backend/)
  - Copy the Railway config (see reference below)
  - Defines how Railway should run the worker service

<details>
<summary>📄 Code for worker.celery.railway.json</summary>

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "pip install -r requirements.txt"
  },
  "deploy": {
    "startCommand": "celery -A backend.celery_app worker --loglevel=info --concurrency=2 --max-tasks-per-child=10",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```
</details>

---

- [x] **3.2 Update Environment Variables**
  - Add to `backend/.env`:
    ```bash
    REDIS_URL=redis://localhost:6379/0
    ```
  - For Railway: Redis plugin will auto-inject `REDIS_URL`

---

### Phase 4: Local Setup & Testing

- [x] **4.1 Install Redis Locally**
  - Choose ONE option below:

  **Option A: Homebrew (macOS) - Recommended**
  ```bash
  brew install redis
  brew services start redis
  redis-cli ping  # Should return "PONG"
  ```

  **Option B: Manual Download**
  ```bash
  wget https://download.redis.io/redis-stable.tar.gz
  tar xzf redis-stable.tar.gz
  cd redis-stable
  make
  src/redis-server  # Starts on port 6379
  ```

---

- [x] **4.2 Start Celery Worker**
  - Open a terminal window
  - Navigate to backend directory: `cd backend`
  - Start worker:
    ```bash
    celery -A celery_app worker --loglevel=info --concurrency=2
    ```
  - Keep this terminal running
  - You should see: `celery@hostname ready.`

---

- [ ] **4.3 Test Dispatch CLI (Small Batch)**
  - Open a **new** terminal window
  - Test with 5 games:
    ```bash
    python backend/cli/dispatch_games.py \
        --model_a "gpt-4o-mini-2024-07-18" \
        --model_b "claude-3-haiku-20240307" \
        --count 5 \
        --monitor
    ```
  - Expected: Models load → Tasks queue → Progress bar → Games complete
  - Check: Games saved to database

---

### Phase 5: Verification

- [ ] **5.1 Test Backwards Compatibility**
  - Verify existing scripts still work:
    ```bash
    # Test single game
    python backend/main.py --models gpt-4o-mini-2024-07-18 claude-3-haiku-20240307

    # Test evaluation
    python backend/cli/evaluate_model.py --model gpt-4o-mini-2024-07-18 --games 3

    # Test worker
    python backend/cli/run_evaluation_worker.py --model gpt-4o-mini-2024-07-18
    ```
  - All should work without errors

---

- [ ] **5.2 Test Parallel Execution**
  - Start worker in one terminal
  - Dispatch 10 games in another terminal with `--monitor`
  - Observe: Games execute in parallel (2 at a time with concurrency=2)
  - Verify: All 10 games complete successfully

---

- [ ] **5.3 Verify Database Persistence**
  - After running games, check database:
    ```bash
    sqlite3 backend/snakebench.db "SELECT COUNT(*) FROM games WHERE created_at > datetime('now', '-1 hour');"
    ```
  - Should show the games you just ran

---

- [ ] **5.4 Test Health Check**
  - Check worker status:
    ```bash
    celery -A backend.celery_app inspect active
    celery -A backend.celery_app inspect stats
    ```
  - Should show worker info and statistics

---

### Phase 6: Railway Deployment

- [ ] **6.1 Add Redis Plugin to Railway**
  - Go to Railway project dashboard
  - Click "New" → "Database" → "Add Redis"
  - Note: `REDIS_URL` is auto-injected into all services

---

- [ ] **6.2 Create Worker Service on Railway**
  - Click "New" → "Empty Service"
  - Name: "celery-worker"
  - Connect to your GitHub repo
  - Set root directory: `backend/`
  - Railway config: Point to `worker.celery.railway.json`
  - Environment variables (auto-inherited):
    - `REDIS_URL` (from Redis plugin)
    - `DATABASE_URL` (from Postgres plugin)
    - All API keys (OpenAI, Anthropic, etc.)

---

- [ ] **6.3 Deploy and Verify**
  - Push code to GitHub
  - Railway auto-deploys
  - Check worker logs: Should show "celery@hostname ready"
  - Test from local: Dispatch games to production
    ```bash
    REDIS_URL=<production_redis_url> python backend/cli/dispatch_games.py \
        --model_a gpt-4o-mini-2024-07-18 --model_b claude-3-haiku-20240307 --count 20
    ```

---

- [ ] **6.4 Scale Workers (Optional)**
  - In Railway dashboard, increase replicas
  - 1 replica = 2 concurrent games
  - 5 replicas = 10 concurrent games
  - Monitor performance and adjust

---

## 🎯 Success Criteria

When complete, you should be able to:

- ✅ Run existing scripts (`main.py`, `evaluate_model.py`) without any changes
- ✅ Dispatch 100+ games via `dispatch_games.py` CLI
- ✅ See games execute in parallel across workers
- ✅ Monitor real-time progress with the progress bar
- ✅ All games persist to database as before
- ✅ Scale to 10+ workers on Railway

---

## 📚 Quick Reference Commands

### Local Development
```bash
# Start Redis
brew services start redis

# Start worker (Terminal 1)
cd backend
celery -A celery_app worker --loglevel=info --concurrency=2

# Dispatch games (Terminal 2)
python backend/cli/dispatch_games.py --model_a "gpt-4" --model_b "claude-3" --count 10 --monitor

# Check worker status
celery -A backend.celery_app inspect active

# Check queue depth
celery -A backend.celery_app inspect reserved

# Stop Redis
brew services stop redis
```

### Monitoring
```bash
# Install Flower (web UI for Celery)
pip install flower

# Start Flower
celery -A backend.celery_app flower --port=5555
# Visit http://localhost:5555
```

### Troubleshooting
```bash
# Test Redis connection
redis-cli ping  # Should return "PONG"

# Check environment variable
echo $REDIS_URL

# View worker logs with debug level
celery -A backend.celery_app worker --loglevel=debug

# Purge all tasks from queue
celery -A backend.celery_app purge
```

---

## 📊 Performance Expectations

| Workers | Concurrency | Parallel Games | Throughput (games/min) |
|---------|-------------|----------------|------------------------|
| 1       | 2           | 2              | 2-4                    |
| 3       | 2           | 6              | 6-12                   |
| 5       | 2           | 10             | 10-20                  |
| 10      | 2           | 20             | 20-40                  |

*Note: Actual throughput depends on model response time*

---

## 🐛 Common Issues

### Issue: Worker can't connect to Redis
**Solution**:
- Check Redis is running: `redis-cli ping`
- Check `REDIS_URL` environment variable
- Test connection: `python -c "import redis; r = redis.from_url('redis://localhost:6379/0'); print(r.ping())"`

### Issue: Tasks stuck in PENDING
**Solution**:
- Check workers are running: `celery -A backend.celery_app inspect active`
- Check queue name matches in `celery_app.py` and `tasks.py`

### Issue: High memory usage
**Solution**:
- Reduce `max-tasks-per-child` in worker command
- Change from `--max-tasks-per-child=10` to `--max-tasks-per-child=5`

---

## 📁 Files Summary

### New Files (4 total)
1. `backend/celery_app.py` - Celery configuration
2. `backend/tasks.py` - Game execution task wrapper
3. `backend/cli/dispatch_games.py` - Mass-parallel dispatcher CLI
4. `worker.celery.railway.json` - Railway worker deployment config

### Modified Files (1 total)
1. `backend/requirements.txt` - Add celery[redis] and redis

### Unchanged Files
- `backend/main.py` - No changes (backwards compatible)
- `backend/cli/evaluate_model.py` - No changes
- `backend/cli/run_evaluation_worker.py` - No changes
- All other existing files - No changes

---

## ✨ Next Steps After Implementation

- [ ] Install Flower for web-based monitoring
- [ ] Set up automated health checks
- [ ] Implement priority queues (urgent vs batch games)
- [ ] Add cost tracking per batch
- [ ] Create performance dashboards
- [ ] Set up alerts for worker failures

---

**Total Implementation Time**: ~2-3 hours
**Risk Level**: Low (fully backwards compatible)
**Value**: Unlock ability to run 1000+ games in parallel
