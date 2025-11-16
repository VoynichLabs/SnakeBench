# Upgrade Migration: Dynamic Models, Event-Driven ELO, and API

Scope: Move from file-based, batch-processed stats to an event-driven, database-backed system that auto-discovers models, evaluates them with a 10-game pipeline, and serves leaderboard and match data via API.

This document evaluates the proposed architecture against the current repo and notes edits where I’d implement things differently. A concrete, phased migration path follows.

---

## Evaluation Of Proposed Actions

1) Replace YAML With Dynamic Model Registry
- Current state: `backend/utils/utils.py` loads `backend/model_lists/model_list.yaml` into memory; all model selection, pricing, and provider info is static.
- Proposal recap: Add a models table and sync with OpenRouter to auto-discover models; store rich metadata and test statuses.
- My approach (edits):
  - Keep YAML as a bootstrap/override source of truth for a short period. Use it to seed the initial DB and for any manual overrides (e.g., pricing deltas, custom kwargs) while the sync matures.
  - Introduce a `models` table with these fields at minimum: `id`, `name` (internal alias used across code), `provider`, `model_slug` (API slug, e.g., `openai/gpt-5-mini`), `pricing_input`, `pricing_output`, `max_completion_tokens`, `metadata_json`, `elo_rating`, `wins`, `losses`, `ties`, `apples_eaten`, `games_played`, `test_status` (untested/testing/ranked/retired), `is_active`, `discovered_at`, `last_played_at`.
  - Add a `sync_openrouter` task that imports models and updates pricing/context length. Respect allow/deny flags in DB (do not auto-activate everything).
  - Rationale: preserves your current workflows while enabling automatic discovery and richer metadata.

2) Shift From Batch Post-Processing To Event-Driven Updates
- Current state: `backend/elo_tracker.py` recalculates ratings and writes `completed_games/stats.json`, `stats_simple.json`, and `game_index.json` off of the replay files. `backend/app.py` serves endpoints backed by these files.
- Proposal recap: On game completion, update the database immediately: insert a game row, participants, and incremental ELO; the DB becomes the source of truth.
- My approach (edits):
  - Keep JSON replays for visualization and debugging; treat them as immutable artifacts referenced by path in DB (`replay_path`).
  - Introduce a `data_access` module for DB writes/reads. From `backend/main.py` after `save_history_to_json`, also persist: `games` row + `game_participants` rows, then calculate and persist ELO and aggregates (wins/losses/ties/apples/games_played) for each involved model.
  - Preserve `elo_tracker.py` as a backfill/validator that can recompute canonical ELO from scratch if needed, and to import historical files during migration.
  - Use the exact same Elo math as today (K=32, pairwise expected/actual as in `backend/elo_tracker.py`) to avoid drift.

3) Model Testing Pipeline (10 Games → Ranked)
- Current state: `backend/cli/evaluate_model.py` already runs a limited-game adaptive opponent selection, but it relies on the file-based `stats_simple.json` and calls `elo_tracker.py` after each game to refresh.
- Proposal recap: Discovery queues untested models; run 10 matches around the median ELO; promote to ranked; skip expensive models.
- My approach (edits):
  - Reuse the selection logic from `backend/cli/evaluate_model.py`, but read/write from the DB instead of JSON files. Keep the “start at median ELO, move up/down by results” behavior.
  - Add a simple `evaluation_queue` table to enqueue (model_id, attempts_remaining, status) and a small worker process (could be a CLI that pulls one job at a time) to run the games.
  - Cost control is enforced before enqueuing: compute estimated per-game cost from known pricing and skip if above a configured threshold. We can add per-provider caps later when token accounting exists.

4) Decouple Frontend From Batch-Generated Files
- Current state: `backend/app.py` serves file-backed endpoints:
  - `GET /api/games` reads `completed_games/game_index.json` and then opens individual replays.
  - `GET /api/stats?simple=true` returns `completed_games/stats_simple.json`; full stats require a `model` param and read `stats.json`.
- Proposal recap: Replace with DB-backed endpoints that serve models, stats, games, and game details; keep replays as files.
- My approach (edits):
  - Maintain current endpoints for compatibility during migration, but progressively switch their internals to query the DB.
  - Add new DB-backed endpoints:
    - `GET /api/models` → all models with aggregates and ELO (replaces `stats_simple.json`).
    - `GET /api/models/{id|name}` → detailed model stats and recent games.
    - `GET /api/games` → paginated list from `games` + `game_participants`.
    - `GET /api/games/{id}` → loads replay via `replay_path` for visualization.
  - Once the frontend swaps to these, remove dependency on the stats files.

5) Minimal Schema Design (Adapted To Repo)
- `models`
  - Keys: `id` (PK), `name` (unique), `provider`, `model_slug` (unique), `is_active` (bool), `test_status` (enum), `discovered_at`, `last_played_at`.
  - Aggregates: `elo_rating` (float, default 1500), `wins`, `losses`, `ties`, `apples_eaten`, `games_played`.
  - Pricing/meta: `pricing_input`, `pricing_output`, `max_completion_tokens`, `metadata_json`.
- `games`
  - Keys: `id` (PK, UUID), `start_time`, `end_time`, `rounds`, `replay_path`, `board_width`, `board_height`, `num_apples`, `total_score`, `created_at`.
- `game_participants`
  - Keys: `id` (PK), `game_id` (FK), `model_id` (FK), `player_slot` (0/1), `score`, `result` (won/lost/tied), `death_round`, `death_reason`.
- Indexing
  - `games.start_time`, `games.end_time` for recency; `game_participants.model_id` for per-model lookups; `models.elo_rating` for leaderboard.

---

## Migration Path (Phased)

Phase 1: Database Foundation
- Add SQLite (stays local-friendly; can move to Postgres later). Define the 3 tables above.
- **Railway deployment**: Use a Railway volume for the SQLite database file to persist data across deployments. Store the database at a volume-mounted path (e.g., `/data/llmsnake.db`) rather than in the application directory, ensuring code updates don't overwrite the database.
- Write a one-time importer:
  - Seed `models` from `backend/model_lists/model_list.yaml` with `is_active=true` only for models you want right away.
  - Import historical replays from `backend/completed_games/*.json`. For each:
    - Insert `games` row with `replay_path` pointing to the JSON file.
    - Insert two `game_participants` rows (or N for N-snake). Use the existing result mapping from `backend/elo_tracker.py`.
  - After ingest, run a “recompute ELO from scratch” pass using the same algorithm in `backend/elo_tracker.py` to initialize `models.elo_rating` and aggregates.

Phase 2: Event-Driven ELO + Aggregates
- In `backend/main.py`, after `save_history_to_json`, add DB writes:
  - Append `games` + `game_participants` rows.
  - Incrementally compute and persist ELO and aggregates (wins/losses/ties/apples/games_played) for each participant using the same math as the batch script.
- Keep `backend/elo_tracker.py` available for validation and as a fallback.

Phase 3: API Layer ✅ COMPLETED
- ✅ In `backend/app.py`, progressively replace file reads with DB queries while keeping response shapes stable. Add new endpoints for models and paginated games.
  - ✅ Created `backend/data_access/api_queries.py` with database query functions
  - ✅ Added new `GET /api/models` endpoint for leaderboard data
  - ✅ Added new `GET /api/models/<model_name>` endpoint for model details
  - ✅ Updated `GET /api/games` to query database and load replays via replay_path
  - ✅ Updated `GET /api/stats` (both simple and model-specific) to use database
  - ✅ Updated `GET /api/matches/<match_id>` to load game metadata from DB
- ✅ Ensure the game detail endpoint returns the same replay schema, loading the replay JSON via `replay_path`.
- ✅ All endpoints tested successfully with existing data (63 models, 3577 games)

Phase 4: Model Discovery + Initial Evaluation ✅ COMPLETED
- ✅ Added `backend/cli/sync_openrouter_models.py` to pull OpenRouter's catalog and upsert into `models` (inactive by default). Respects pricing caps and budget limits.
- ✅ Added `evaluation_queue` table and a worker (`backend/cli/run_evaluation_worker.py`) that:
  - Picks `untested` models, runs 10 games using the adaptive opponent selection (DB-backed), updates ELO and sets `test_status='ranked'` when done.
- ✅ Enforces budget checks before enqueuing jobs with conservative cost estimation.

Phase 5: Automation + Scheduling
- Add a periodic sync (cron/systemd/GitHub Actions/host scheduler) to:
  - Run the OpenRouter sync.
  - Enqueue untested models up to a budget cap.
  - Optionally rotate regular matchmaking to keep ratings fresh.

---

## Quick Wins (Order Of Impact)
- Import historical data into SQLite and verify leaderboards from DB match `stats_simple.json` ordering.
- Wire `backend/app.py` to serve models/games from DB while still using replay files by path.
- Reuse `backend/cli/evaluate_model.py` logic with DB reads/writes to establish the 10-game pipeline fast.

---

## Compatibility And Cutover
- During migration, continue emitting `stats.json`, `stats_simple.json`, and `game_index.json` until the frontend fully switches to the DB-backed endpoints.
- Keep replay files as-is; only the source of truth for stats moves to the DB.
- Add a `recompute_elo` maintenance command to rebuild ratings if any historic data changes.

---

## Open Questions Resolved
- **Expected cadence/volume of new OpenRouter models**: Daily cron job is sufficient.
- **SQLite timeline**: SQLite is acceptable for production. No immediate Postgres migration needed.
- **Policy for auto-retiring models**: TBD later; will create a policy for retiring models that consistently fail or are not working.
- **Seed for reproducibility**: Not needed. Games are not meant to be replayed deterministically; replays provide sufficient history.

---

## Repo-Specific Notes
- Files relying on YAML today: `backend/utils/utils.py`, `backend/run_batch.py`, `backend/cli/evaluate_model.py`.
- Batch ELO and file outputs: `backend/elo_tracker.py`, emits `completed_games/stats.json`, `stats_simple.json`, `game_index.json`.
- Game writes: `backend/main.py` persists replays to `backend/completed_games/`; we will add DB persistence at the same time.
- API surface to evolve: `backend/app.py` currently reads files; target is DB for models/stats and file path for replays.

