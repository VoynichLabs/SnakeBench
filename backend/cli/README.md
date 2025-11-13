# CLI Tools

This directory contains command-line utilities for managing the LLMSnake evaluation system.

## Model Discovery and Evaluation (Phase 4)

### sync_openrouter_models.py

Synchronizes the local database with OpenRouter's model catalog.

**Features:**
- Fetches all available models from OpenRouter API
- Adds new models with `is_active=false` and `test_status='untested'`
- Updates pricing and metadata for existing models
- Preserves model stats (ELO, win/loss records) during updates
- Optional auto-queueing with budget controls

**Usage:**

```bash
# Basic sync (no auto-queue)
python backend/cli/sync_openrouter_models.py

# With OpenRouter API key
python backend/cli/sync_openrouter_models.py --api-key YOUR_API_KEY

# Or set environment variable
export OPENROUTER_API_KEY=YOUR_API_KEY
python backend/cli/sync_openrouter_models.py

# Auto-queue models for evaluation (within budget)
python backend/cli/sync_openrouter_models.py --auto-queue --budget 10.0 --max-cost-per-game 0.50
```

**Options:**
- `--api-key <key>` - OpenRouter API key (or use OPENROUTER_API_KEY env var)
- `--auto-queue` - Automatically queue untested models within budget
- `--budget <amount>` - Total budget for auto-queueing (default: $10.00)
- `--max-cost-per-game <amount>` - Maximum cost per game (default: $0.50)

**Cost Controls:**
- Estimates cost per game based on model pricing (conservative: 1000 input + 500 output tokens)
- Queues cheapest models first
- Stops when budget limit reached
- Skips models without pricing data

---

### run_evaluation_worker.py

Processes models from the evaluation queue.

**Features:**
- Pulls queued models and runs 10 evaluation games
- Adaptive opponent selection (starts at median ELO, adjusts based on results)
- Fully database-backed (no dependency on YAML or JSON files)
- Updates ELO and model stats automatically
- Marks models as 'ranked' upon completion
- Supports continuous mode for automation

**Usage:**

```bash
# Process one queued model
python backend/cli/run_evaluation_worker.py

# Run continuously (keep checking for new jobs)
python backend/cli/run_evaluation_worker.py --continuous --interval 60

# Custom game parameters
python backend/cli/run_evaluation_worker.py --width 10 --height 10 --max-rounds 100 --num-apples 5
```

**Options:**
- `--continuous` - Run continuously, checking for new jobs
- `--interval <seconds>` - Seconds between checks in continuous mode (default: 60)
- `--width <n>` - Board width (default: 10)
- `--height <n>` - Board height (default: 10)
- `--max-rounds <n>` - Maximum rounds per game (default: 100)
- `--num-apples <n>` - Number of apples on board (default: 5)

**Process:**
1. Retrieves next queued model (FIFO order)
2. Builds model config from database
3. Runs 10 games with adaptive opponent selection:
   - First game: opponent near median ELO
   - After win: higher-rated opponent
   - After loss: lower-rated opponent
   - Prefers unplayed opponents
4. Updates ELO and stats after each game (via main.py)
5. Marks model as 'ranked' when complete

---

### test_queue_workflow.py

Tests the evaluation queue workflow without running actual games.

**Features:**
- Verifies queue operations
- Tests status updates
- Checks model config building
- Validates opponent availability

**Usage:**

```bash
python backend/cli/test_queue_workflow.py
```

**Checks:**
- ✓ Queue statistics
- ✓ Model retrieval from queue
- ✓ Status updates (queued → running → done/failed)
- ✓ Model config building from database
- ✓ Ranked model count (available opponents)

---

## Legacy Tools (Pre-Phase 4)

### evaluate_model.py

Standalone model evaluation using file-based stats.

**Note:** For new evaluations, use the queue-based system (sync + worker) instead.

**Usage:**
```bash
python backend/cli/evaluate_model.py --model <model_name> --games 10
```

---

### generate_matchups.py

Generate scheduled matchmaking games.

**Usage:**
```bash
python backend/cli/generate_matchups.py
```

---

## Typical Workflow

### Initial Setup

1. **Initialize database:**
   ```bash
   python backend/database.py
   ```

2. **Sync models from OpenRouter:**
   ```bash
   python backend/cli/sync_openrouter_models.py --auto-queue --budget 5.0
   ```

3. **Check queue:**
   ```bash
   python backend/cli/test_queue_workflow.py
   ```

### Daily Operations

1. **Sync new models** (run daily via cron):
   ```bash
   python backend/cli/sync_openrouter_models.py --auto-queue --budget 10.0
   ```

2. **Process evaluations** (run as background service):
   ```bash
   python backend/cli/run_evaluation_worker.py --continuous --interval 300
   ```

### Manual Queue Management

**Add model to queue manually:**
```python
from data_access import enqueue_model
enqueue_model(model_id=123, attempts=10)
```

**Check queue stats:**
```python
from data_access import get_queue_stats
print(get_queue_stats())
# Output: {'queued': 10, 'running': 1, 'done': 50, 'failed': 2}
```

**Remove model from queue:**
```python
from data_access import remove_from_queue
remove_from_queue(model_id=123)
```

**Clear entire queue** (use with caution):
```bash
sqlite3 backend/snakebench.db "DELETE FROM evaluation_queue;"
```

---

## Environment Variables

- `OPENROUTER_API_KEY` - Your OpenRouter API key for sync operations
- `RAILWAY_ENVIRONMENT` - Set by Railway to use production database path

---

## Database Paths

- **Local development:** `backend/snakebench.db`
- **Railway (production):** `/data/snakebench.db` (requires volume mount)

---

## Cost Monitoring

The system uses conservative cost estimates. Monitor actual costs and adjust budgets:

**Default estimates:**
- Input tokens per game: 1000
- Output tokens per game: 500

**Recommended budgets:**
- Testing: $1-5
- Daily operations: $10-50
- Bulk evaluation: $50-200

**To adjust:**
```bash
# Lower per-game limit for cheaper models only
python backend/cli/sync_openrouter_models.py --auto-queue --max-cost-per-game 0.10

# Higher total budget for more models
python backend/cli/sync_openrouter_models.py --auto-queue --budget 50.0
```

---

## Troubleshooting

**Sync fails with "No API key":**
- Set `OPENROUTER_API_KEY` environment variable
- Or use `--api-key` flag

**Worker can't find opponents:**
- Ensure you have ranked models (from Phase 1-3)
- Check: `SELECT COUNT(*) FROM models WHERE test_status = 'ranked';`

**Queue seems stuck:**
- Check queue stats: `python backend/cli/test_queue_workflow.py`
- Look for 'failed' entries: `SELECT * FROM evaluation_queue WHERE status = 'failed';`
- Clear failed entries if needed: `DELETE FROM evaluation_queue WHERE status = 'failed';`

**Model evaluation fails:**
- Check model config in database
- Verify model is actually available on OpenRouter
- Some models may require special configuration or API access

---

## Next Steps (Phase 5)

- Set up cron jobs for daily sync
- Deploy worker as background service
- Add monitoring and alerts
- Create admin API for queue management

---

For more details, see:
- `docs/phase4-completion-summary.md`
- `docs/upgrade-steps.md`
