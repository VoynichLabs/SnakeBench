# CLI Tools (Celery-Only)

Command-line helpers for the LLMSnake backend. The system now runs games exclusively through the Celery + Redis pipeline; legacy evaluation-queue and local thread runners have been removed.

## sync_openrouter_models.py
- Syncs OpenRouter catalog into the database (adds/updates model metadata only).
- Usage:
  - `python backend/cli/sync_openrouter_models.py`
  - `python backend/cli/sync_openrouter_models.py --api-key YOUR_API_KEY`

## dispatch_games.py
- Submits game tasks to the Celery queue for worker execution.
- Usage:
  - `python backend/cli/dispatch_games.py --model_a gpt-4 --model_b claude-3 --count 10`
  - Add `--monitor` to watch task progress.
- Game params: `--width`, `--height`, `--max_rounds`, `--num_apples`.

## generate_matchups.py
- Generates matchup lists for bulk scheduling.
- Usage examples:
  - `python backend/cli/generate_matchups.py --mode all --rounds 3`
  - `python backend/cli/generate_matchups.py --mode single --model my_model --rounds 3`

## evaluate_models.py
- Orchestrates binary-search style evaluations for untested/testing models (game_type='evaluation').
- Usage:
  - `python backend/cli/evaluate_models.py --max-models 5 --max-games 10`
  - Optional board params: `--width`, `--height`, `--max-rounds`, `--num-apples`.
  - Picks up from history if rerun; dispatches one eval game per model per run.

## Other scripts
- `cleanup_stale_games.py`, `reset_database.py`, `undo_game.py`, `generate_video.py` remain available for maintenance/video export tasks.

## Flow overview
1) Sync models (`sync_openrouter_models.py`).
2) Start Redis + Celery workers (include the video queue):  
   `celery -A celery_app worker --loglevel=info -Q celery,video`
3) Dispatch games (`dispatch_games.py` or your scheduler that enqueues `backend.tasks.run_game_task`).
