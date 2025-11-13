# Upgrade Steps: Checklist And Playbook

This is a pragmatic, step-by-step checklist to implement the migration. It’s organized in small, verifiable steps you can repeat and roll out incrementally. No code is included here; it references where to make changes.

---

## Phase 1 — Database Foundation
- [x] Choose SQLite file path for local: `backend/llmsnake.db`.
- [x] **Railway volume setup**:
  - [x] Create a Railway volume mounted at `/data` (or your preferred path).
  - [x] Configure the app to use `/data/llmsnake.db` when running on Railway (detect via environment variable, e.g., `RAILWAY_ENVIRONMENT`).
  - [x] Ensure the database path falls back to `backend/llmsnake.db` for local development.
  - [x] Add to `.gitignore`: `backend/llmsnake.db` and `/data/` to prevent committing local database files.
- [x] Create tables: `models`, `games`, `game_participants` as defined in upgrade-migration.md.
- [x] Seed models from YAML:
  - [x] Write a one-time script to load `backend/model_lists/model_list.yaml` and upsert rows in `models` (set `is_active` explicitly, default false if unsure).
  - [x] Preserve: `name`, `provider`, `model_slug`, `pricing_*`, `max_completion_tokens`, any config kwargs into `metadata_json`.
- [x] Import historical games:
  - [x] Scan `backend/completed_games/*.json` and insert rows into `games` with `replay_path` set.
  - [x] For each replay, create two `game_participants` rows using metadata fields (scores, result, death info).
- [x] Initialize ratings and aggregates:
  - [x] Run a one-time "recompute ELO" pass using the same math in `backend/elo_tracker.py` (K=32; pairwise expected/actual). Persist `elo_rating`, `wins`, `losses`, `ties`, `apples_eaten`, `games_played` on `models`.
  - [x] Verify leaderboard ordering vs. `completed_games/stats_simple.json`.

Acceptance checks:
- [x] Can query `models` ordered by `elo_rating` and get a sensible leaderboard.
- [x] Spot check a few models' aggregates against `stats.json`.

---

## Phase 2 — Event-Driven ELO And Aggregates
- [x] Add a small DB layer in `backend/data_access/` for: insert game, insert participants, update model aggregates, update ELO.
- [x] In `backend/main.py`, after `save_history_to_json`, also:
  - [x] Insert `games` and `game_participants` rows with the same `game_id`.
  - [x] Compute incremental ELO and update aggregates for both participants.
- [x] Keep `backend/elo_tracker.py` for validation/backfill.

Acceptance checks:
- [x] Run a single game via `backend/main.py`; confirm DB rows are created and ELO changes match a subsequent `elo_tracker.py` recompute.

---

## Phase 3 — API Layer (DB-Backed)
- [x] Create `backend/data_access/api_queries.py` with database query functions:
  - [x] `get_all_models()` - retrieve all models with stats sorted by ELO
  - [x] `get_model_by_name()` - get single model details
  - [x] `get_games()` - paginated game list with participants
  - [x] `get_game_by_id()` - single game lookup
  - [x] `get_total_games_count()` - total games count
- [x] In `backend/app.py`, add DB-backed reads for:
  - [x] `GET /api/models` → model list with aggregates and current ELO.
  - [x] `GET /api/models/{id|name}` → one model's stats and recent games.
  - [x] `GET /api/games?limit=&offset=&sort_by=` → recent games from DB, loads replays via replay_path.
  - [x] `GET /api/matches/{id}` → load replay via `replay_path` from DB.
- [x] Updated existing endpoints to use database:
  - [x] `GET /api/stats?simple=true` → now queries database instead of stats_simple.json
  - [x] `GET /api/stats?model=<name>` → now queries database instead of stats.json
- [x] Response formats maintained for frontend compatibility.

Acceptance checks:
- [x] All endpoints tested successfully with existing data (63 models, 3577 games).
- [x] Replay details load from file path stored in DB.
- [x] Response shapes match previous JSON file format for compatibility.

---

## Phase 4 — Model Discovery And Initial Evaluation ✅ COMPLETED
- [x] Add `backend/cli/sync_openrouter_models.py`:
  - [x] Pull OpenRouter catalog; upsert into `models` with `is_active=false` by default.
  - [x] Update pricing/context fields and set `discovered_at`.
- [x] Add evaluation queue:
  - [x] Create `evaluation_queue` table with fields: `model_id`, `status` (queued/running/done/failed), `attempts_remaining` (default 10), timestamps.
  - [x] Add a small worker (CLI) that pops one queued model and runs 10 evaluation games using the adaptive selection logic from `backend/cli/evaluate_model.py` but backed by DB.
  - [x] On completion, set `test_status='ranked'` and optionally `is_active=true`.
- [x] Cost control:
  - [x] Before queueing, compute an estimated per-game cost from `pricing_*` and a conservative token estimate; skip above threshold.

Acceptance checks:
- [x] Running the sync adds new models to DB without breaking existing ones.
- [x] Queueing a model leads to 10 DB-backed games and updates ELO and aggregates.

---

## Phase 5 — Automation And Ops
- [ ] Add a scheduler (cron/systemd/CI or Railway Cron) to:
  - [ ] Run **daily** OpenRouter sync (once per day is sufficient).
  - [ ] Enqueue untested models within budget.
  - [ ] Optionally schedule periodic regular matchmaking.
- [ ] Add a `recompute_elo` maintenance command to rebuild ratings from all historical games.
- [ ] Add minimal monitoring/logging (e.g., counts of models by test_status, last sync time).

Acceptance checks:
- [ ] Daily sync/queue runs without manual intervention.
- [ ] Leaderboard stays fresh; replays still accessible.

---

## Rollback/Compatibility Plan
- [ ] Keep writing `stats.json`, `stats_simple.json`, and `game_index.json` until the frontend is switched.
- [ ] If needed, toggle a config flag to temporarily disable DB writes and fall back to batch `elo_tracker.py`.
- [ ] Keep `elo_tracker.py` as the source of “authoritative recompute” until DB parity is proven.

---

## Notes On Repo Touch Points
- `backend/main.py`: add DB persistence and incremental ELO at end of each game.
- `backend/elo_tracker.py`: keep intact for import/backfill/validation.
- `backend/app.py`: evolve endpoints to DB-backed reads; keep replay files.
- `backend/utils/utils.py`: stop being the primary source for models after seeding; DB becomes the source of truth.
- `backend/cli/evaluate_model.py`: reuse opponent selection, but convert reads/writes to DB.

