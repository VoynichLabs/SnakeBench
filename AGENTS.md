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


Findings & Reflections
Key Observations
• LLMs often misinterpreted the board layout provided in text format. This led to cases where models incorrectly believed where their snake's head was or caused the snake to run into their own tail.
• Lower-tier models (including GPT-3.5 Turbo and Haiku) struggled significantly, while GPT-4, Gemini 2.0, and o3-mini showed a baseline performance that allowed for an interesting game.
• Context is key, you need to load the LLM up with a lot of information for it to make a good choice. Board position, apple location, other snakes position, etc.
Methodology
• The board was provided in a textual format. This required the prompt to be explicit about the XY coordinate system. Without a true 2D representation, spatial reasoning was often lost in translation.
• Each LLM took turns simultaneously. The turn-based mechanics highlighted internal chain-of-thought processes. I saved the model responses for analysis.
Analysis
• The text-based board representation proved challenging for LLMs. Since the board is treated as tokens rather than a true 2D map, models often misjudged positions and made erroneous moves, such as running into walls or colliding with themselves.
• While one idea was to restrict models to only legal moves to prevent such errors, doing so might narrow their strategic playing field, effectively handicapping their natural decision-making.
Future Work
• With better models, use bigger board sizes.
• Add more snakes, more apples, and add walls to the game.
Other Notes
• Google models experienced unexpected rate limits despite being on a paid tier, resulting in fewer results and prompting a deeper dive into GCP settings.
Prompt Example
You are controlling a snake in a multi-apple Snake game.The board size is 10x10. Normal X,Y coordinates are used. Coordinates range from (0,0) at bottom left to (9,9) at top right.

Apples at: (9, 6), (0, 2), (5, 9), (1, 7), (9, 7)

Your snake ID: 1 which is currently positioned at (5, 1)

Enemy snakes positions:
* Snake #2 is at position (7, 1) with body at []

Board state:

9 . . . . . A . . . .
8 . . . . . . . . . .
7 . A . . . . . . . A
6 . . . . . . . . . A
5 . . . . . . . . . .
4 . . . . . . . . . .
3 . . . . . . . . . .
2 A . . . . . . . . .
1 . . . . . 1 . 2 . .
0 . . . . . . . . . .
  0 1 2 3 4 5 6 7 8 9

--Your last move information:--

Direction: LEFT

Rationale: I'm noticing that (0,2) is the closest apple from our head at (6,1) (it's 7 steps away by Manhattan distance), and it's away from the enemy snake at (7,0). Right now our immediate options are:

• UP → goes to (6,2)
• RIGHT → goes to (7,1) (closer to the enemy snake's territory)
• LEFT → goes to (5,1)
• DOWN → goes to (6,0)

Moving RIGHT or DOWN brings us closer to the enemy snake at (7,0) or even out of safe bounds. Moving UP would work, but LEFT starts guiding us toward (0,2). Thus, I decide to move LEFT.

Strategy for future turns: I'll aim to continue left and then maneuver upward to reach the apple at (0,2) while remaining mindful of potential enemy moves.

My decided next move: LEFT.

--End of your last move information.--

Rules:
1) If you move onto an apple, you grow and gain 1 point.
    
2) If you run into a wall (outside the range of the listed coordinates), another snake, or yourself (like go backwards), you die.

3) The goal is to have the most points by the end.

Decreasing your x coordinate is to the left, increasing your x coordinate is to the right.

Decreasing your y coordinate is down, increasing your y coordinate is up.

You may think out loud first then respond with the direction.

You may also state a strategy you want to tell yourself next turn.

End your response with your decided next move: UP, DOWN, LEFT, or RIGHT.