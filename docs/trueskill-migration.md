Migrating from ELO to TrueSkill (Truescale)
===========================================

Context and goals
-----------------
- Current ladder uses a home-grown ELO (K=32, INITIAL=1500) updated per game via pairwise comparisons. Ratings live in `models.elo_rating` and are surfaced by `backend/app.py` (`/api/models`, `/api/stats`, etc.), and the frontend ranks by that field.
- The update path is `backend/main.py.persist_to_database()` -> `data_access.model_updates.update_elo_ratings()` -> `ModelRepository.update_elo_ratings_for_game()`. The rollback path in `backend/cli/undo_game.py` also replays ELO chronologically. Queries/ranks in `GameRepository` and stats endpoints use `ROW_NUMBER() OVER (ORDER BY elo_rating DESC)`.
- We want to replace ELO with TrueSkill (Python library `trueskill`/"Truescale"), expose ordering by a TrueSkill-derived score, and keep a display-scale (e.g., *mu* x 50) for UI continuity. We will also need backfill, new-player placement, and optional compatibility aliases while the frontend migrates.

Target data model
-----------------
- Add persistent TrueSkill columns on `models`:
  - `trueskill_mu` (double precision, default 25.0)
  - `trueskill_sigma` (double precision, default 25.0/3 ~ 8.333)
  - `trueskill_exposed` (either computed in app code or as a generated column) = `trueskill_mu - 3 * trueskill_sigma` (conservative rating used for ordering).
  - `trueskill_updated_at` (timestamp) for auditing.
- Optional but recommended history table for debugging/backfill verification:
  - `model_rating_history` `(game_id uuid, model_id int, pre_mu, pre_sigma, post_mu, post_sigma, exposed, created_at timestamptz default now(), primary key (game_id, model_id))`.
- Keep `elo_rating` during the transition; populate it from scaled TrueSkill (e.g., `trueskill_exposed * 50`) to avoid breaking existing consumers until the frontend/api payloads are updated.

New rating module
-----------------
- Create a dedicated module (e.g., `backend/services/trueskill_engine.py`) that wraps the library and isolates parameters. Responsibilities:
  - Hold a configured `trueskill.TrueSkill` environment (mu=25, sigma=25/3, beta=25/6, tau small e.g., 0.5, draw_probability ~0.1 unless we want 0 for snake).
  - Provide helpers:
    - `rate_game(game_id)`: fetch participants/results from DB, build Rating objects with current mu/sigma, call `rate()` (supports 2+ players), persist post-game mu/sigma/exposed back to `models` (and history table if present).
    - `conservative(score)` and `display_score(score)` that return exposed and UI-scaled numbers (e.g., `exposed`, `exposed * 50`, or `mu * 50` for the "looks like ELO" requirement).
    - Serialization helpers to/from DB rows.
- Wire `persist_to_database()` (backend/main.py) to call `update_trueskill_ratings(game_id)` instead of `update_elo_ratings`. Mirror this entry point in `data_access/model_updates.py` and `ModelRepository`.
- Expose a single config object so placement logic can read the same mu/sigma defaults and scaling constants.

Backfill plan
-------------
- Implement a CLI `backend/cli/backfill_trueskill.py` that:
  - Resets all models to mu=25.0, sigma=25/3 (and sets `elo_rating` to the scaled exposed for compatibility).
  - Streams games ordered by `start_time ASC NULLS FIRST` (falls back to `end_time` when needed) from `games`, pulls participants from `game_participants`, and applies `rate()` sequentially.
  - Persists post-game mu/sigma/exposed for each participant; optionally records history rows.
  - Emits a summary (min/max/median exposed, sigma distribution, highest-momentum models) to sanity-check.
- This CLI can also serve as the new implementation for `undo_game.py` (replay everything except the target game), removing duplicate rating logic.

API and frontend touchpoints
----------------------------
- API sorting and payloads:
  - `ModelRepository.get_all/get_ranked_models` and `GameRepository` queries should order by `trueskill_exposed` (or `trueskill_mu` if we decide against conservative ordering). Keep a `SELECT ... AS elo_rating` alias for the frontend until it migrates.
  - `/api/models`, `/api/stats`, `/api/games` payloads should include `trueskill_mu`, `trueskill_sigma`, `trueskill_exposed`, and a `display_rating` (mu or exposed scaled by 50). Maintain the existing `elo`/`elo_rating` fields as aliases for one release.
- Frontend changes:
  - `frontend/src/components/home/LeaderboardSection.tsx` and `/models/[id]/page.tsx` currently sort by `elo`; update to consume `display_rating` (or `trueskill_exposed`) and adjust labels to "TrueSkill"/"Truescale".
  - Add a simple scaling helper on the frontend for experiments (e.g., allow env override of multiplier) if we decide to keep the scaling purely client-side.

Placement and matchmaking implications
--------------------------------------
- `backend/placement_system.py` currently uses ELO-based intervals; rework to:
  - Use `trueskill_mu` +/- `k * sigma` for targeting (sigma gives natural uncertainty).
  - Prioritize opponents that maximally reduce sigma (high information gain), similar to TrueSkill's built-in quality metric.
  - Seed new players at mu=25, sigma=25/3; after ~9 games, placement can freeze sigma floor or switch them to normal scheduling.
- For game generation or evaluation queues, consider storing a `trueskill_quality` score for candidate matchups (from the library) to avoid low-signal games.

Operational steps (to-do, ordered)
----------------------------------
- [x] Add dependency `trueskill` to `backend/requirements.txt` (pin version, install locally to confirm import).  
- [x] Add DB columns/migrations for `trueskill_mu`, `trueskill_sigma`, `trueskill_exposed`, `trueskill_updated_at`, and optional `model_rating_history`; keep `elo_rating` populated from scaled exposed.  
- [x] Implement `services/trueskill_engine.py` with a configured environment plus `update_trueskill_ratings` entrypoints in the data-access layer.  
- [x] Swap backend write path to call the TrueSkill updater; retain ELO aliases for compatibility during rollout.  
- [x] Build and run `backend/cli/backfill_trueskill.py`; stream games in time order, persist mu/sigma/exposed, and emit sanity-check summaries.  
- [x] Update API queries/payloads to order by and surface TrueSkill fields (`trueskill_exposed`, `display_rating`, aliases for `elo_rating`).  
- [x] Update frontend leaderboard and model pages to read/display the new rating field (apply x50 scaling in UI if we keep it presentational).  
- [x] Replace `undo_game.py` rating logic with the shared backfill/replay implementation to avoid drift.  
- [x] Iterate placement rules using mu/sigma (information gain, sigma floors) and add tests for 2-player and 3+ player games.  

Recommendations on storage location for backfill results
--------------------------------------------------------
- Keep TrueSkill state on `models` (mu/sigma/exposed) for live ranking; store per-game snapshots in `model_rating_history` to make backfill idempotent and auditable.
- If we need to join ratings into game-level analytics, add `pre_mu/pre_sigma/post_mu/post_sigma` columns to `game_participants` (nullable) instead of denormalizing onto `games`.

Open decisions to confirm
-------------------------
1) Leaderboard ordering: conservative rating (`mu - 3*sigma`) vs raw `mu` (default: conservative for stability).  
2) UI scaling: base the x50 display number on `exposed` vs `mu` (default: `exposed * 50` to mimic "safe ELO").  
3) Draw handling: keep `draw_probability = 0.1` or force 0 (default: keep 0.1 and treat ties as true ties).  
Decisions (locked)
------------------
- Ordering: use conservative rating (`mu - 3*sigma`) for leaderboard/ranks.
- UI scaling: use `exposed * 50` for the ELO-ish display number.
- Draw/ties: keep default draw_probability = 0.1, treat ties as true ties.
- Compatibility: keep `elo`/`elo_rating` alias for one release only; then drop and expose a neutral `rating` field (with rating-type metadata) once frontend/API consumers migrate.
