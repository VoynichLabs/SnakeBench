# @AGENTS.md

This is my future-self cheat-sheet for working inside **SnakeBench2**.  Think of it as the concise set of reminders that I’d want to read before touching any feature, debugging a crash, or shipping something new.

## Big picture
- **What happens:** Python backend simulates LLM-controlled snakes on a grid while a Next.js frontend renders leaderboards, replay snippets, and live stats.
- **Data flow:** Games are run via `SnakeGame` → history saved locally/Supabase (`services/supabase_storage`) → aggregated stats/ELO updated (`data_access`) → frontend surfaces the latest matches and leaderboard.
- **LLM stack:** Prompts are built in `players/llm_player.py`, sent through `llm_providers.py` (currently routed through OpenRouter), and outcomes (direction, rationale, token usage, cost) are stored per round.

## Directory map (for quick orientation)
- `backend/` – game engine, Celery tasks, database layer, video tools, CLI helpers.
  - `main.py` (core `SnakeGame` + `run_simulation`)
  - `tasks.py` + `celery_app.py` (distributed execution, video queue)
  - `players/` (`LLMPlayer`, `RandomPlayer`, shared base)
  - `llm_providers.py` (OpenRouter wrapper + factory)
  - `data_access/` (repositories + helpers; failure to import simply disables DB persistence)
  - `services/` (Supabase client/storage, video generator, cron/webhook helpers)
  - `cli/` (matchmaking, dispatch, video backfills, Elo sync)
- `frontend/` – Next.js 15 app/router + Tailwind, renders hero, stats, leaderboard, match viewer, ASCII replay (`AsciiSnakeGame` lives under `components`).
- `docs/` – long Supabase reference notes; not part of runtime but handy when touching hosting/infra.
- Root scripts: `dev.sh`, `run_repomix.sh`, `llms.txt` (model list history).

## Key workflows
1. **Run a quick local match**  
   ```bash
   cd backend
   python3 main.py --models <model-a> <model-b> [--width N --height N]
   ```  
   Ensure `OPENROUTER_API_KEY` (and other LLM keys as needed) are set in `.env.local`.

2. **Scale with Celery/Redis**  
   - Start Redis (`redis-server` or docker).  
   - Launch worker: `celery -A celery_app worker --loglevel=info`.  
   - Dispatch: `python3 cli/dispatch_games.py --model_a ... --model_b ... --count 10 --monitor`.  
   - Video generation runs on the `video` queue via `generate_video_task`.

3. **Frontend dev loop**  
   ```bash
   cd frontend
   npm install
   npm run dev
   ```  
   API hits backend (default `http://localhost:5000`). Adjust `NEXT_PUBLIC_API_URL` if needed.

4. **Data / persistency checks**  
   - Completed games: `backend/completed_games/snake_game_<id>.json`.  
   - Supabase storage uploads via `services/supabase_storage.py`.  
   - Database updates flow through `persist_to_database()` (uses `data_access` modules) → fails silently if DB not reachable.

5. **Testing & linting**  
   - Backend: `pytest` (with `requirements` installed).  
   - Frontend: `npm run lint`, `npm run test` (if tests exist), `npm run build` to catch TS issues.  
   - When touching prompts, re-run a local game to verify LLM fallback logic still works.

## Environment reminders
- **Backend env file:** `backend/.env.local` (also check `dotenv` in `main.py`). Key vars: `OPENROUTER_API_KEY`, `SUPABASE_URL/KEY/DB`, `REDIS_URL`, `CORS_ALLOWED_ORIGINS`, optional OpenRouter headers (`OPENROUTER_SITE_URL`, `OPENROUTER_SITE_NAME`).
- **Frontend env:** `frontend/.env.local` with `NEXT_PUBLIC_API_URL`, PostHog keys.
- **LLM costs:** Pricing stored per model (`pricing_input`/`pricing_output` or nested `pricing` dict). Prompts calculate per-token cost; move history includes `cost` for aggregation.
- **Dependencies:** Backend pinned in `requirements.txt` (Flask 3, Celery/Redis, MoviePy, Supabase, Psycopg2). Use `python -m pip install -r requirements.txt` inside `backend`.

## Troubleshooting notes
- `data_access` imports may fail when Supabase/Postgres credentials are missing – the exception is caught in `main.py`, so you’ll need to inspect logs if persistence is suddenly silent.
- LLM prompts are heavy (`game_state.print_board()`, enemy summaries). If prompts cause rate limits, tweak `LLMPlayer` (there’s fallback to random move) or adjust `max_rounds`/`num_apples`.
- Video generation uses MoviePy + FFmpeg via `services/video_generator.py` and runs asynchronously. If generation hangs, inspect Celery `video` queue logs and ensure FFmpeg is on PATH.
- Celery tasks log retries (`GameTask` base). When debugging, check `celery -A celery_app status` and `redis-cli monitor`.
- Supabase upload failures print `Failed to upload replay` but still writes to `completed_games/`. Look for `replay_storage_path` in JSON metadata.

## TODOs / watchlist (keep this updated if you touch adjacent systems)
- Validate `placement_system.py` math when matchmaking changes; it drives the evaluation CLI (used by `cli/generate_matchups.py`).
- Confirm `services/cron_service.py` schedule matches production; it may enqueue periodic tasks or cleanup.
- If you add new providers, update `llm_providers.py` factory plus `backend/tests` to cover `get_response` parsing.
- When tweaking frontend stats, update backend endpoints in `app.py` or `data_access/api_queries.py` accordingly.

## External references
- `README.md` (project overview + quick start).  
- `CLAUDE.md` (Claude-specific guidance; keep in sync when platform changes).  
- `docs/supabase.md` (long-form Supabase + infra snippets).  
- `llms.txt` (model history/reference when writing matchups).

## Final reminder
Any time you add new `.env` variables, document them here/README and regenerate `.env.local.example` if applicable. Keep `@AGENTS.md` updated with any long-lived gotchas so the next “future self” doesn’t rediscover them.
