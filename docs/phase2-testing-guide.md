# Phase 2 Testing Guide

Quick reference for testing and validating Phase 2 implementation.

---

## Quick Validation (No LLM calls needed)

### 1. Database Integration Test
```bash
cd backend
python3 test_db_integration.py
```

**What it checks:**
- Database schema is correct
- Required columns exist in all tables
- Models are seeded
- data_access module imports successfully

**Expected output:** "Database Integration Test: READY"

---

### 2. Persistence Flow Test
```bash
cd backend
python3 test_phase2_persistence.py
```

**What it tests:**
- Game insertion
- Participant insertion
- Aggregate updates (wins/losses/ties/apples)
- ELO rating calculations

**Expected output:** "Phase 2 Persistence Test: PASSED"

**What happens:**
1. Creates a mock game where model1 wins
2. Verifies database rows created
3. Checks ELO changes (winner gains, loser loses)
4. Cleans up test data and restores original stats

---

### 3. ELO Consistency Validation
```bash
cd backend
python3 validate_elo_consistency.py
```

**What it validates:**
- Compares current DB ELO ratings against full recompute
- Uses exact same algorithm as elo_tracker.py
- Reports any discrepancies

**Expected output:** "✓ VALIDATION PASSED" with max delta near 0.0000

---

## Full Integration Test (With LLM calls)

### Run a Real Game

```bash
cd backend
python3 main.py --models 'gpt-4o-mini-2024-07-18' 'claude-sonnet-4-20250514'
```

**What to verify after game completes:**

1. **JSON replay saved:**
   ```bash
   ls -lh completed_games/snake_game_*.json | tail -1
   ```

2. **Game in database:**
   ```bash
   sqlite3 llmsnake.db "SELECT id, rounds, total_score FROM games ORDER BY created_at DESC LIMIT 1;"
   ```

3. **Participants in database:**
   ```bash
   sqlite3 llmsnake.db "SELECT gp.player_slot, m.name, gp.score, gp.result
   FROM game_participants gp
   JOIN models m ON gp.model_id = m.id
   ORDER BY gp.created_at DESC LIMIT 2;"
   ```

4. **Model stats updated:**
   ```bash
   sqlite3 llmsnake.db "SELECT name, elo_rating, wins, losses, games_played
   FROM models
   WHERE name IN ('gpt-4o-mini-2024-07-18', 'claude-sonnet-4-20250514');"
   ```

5. **Verify ELO changed:** Compare the ELO ratings before and after the game

---

## Debugging

### Check recent games
```bash
sqlite3 llmsnake.db "SELECT id, start_time, rounds, total_score FROM games ORDER BY created_at DESC LIMIT 5;"
```

### Check model ELO history
```bash
sqlite3 llmsnake.db "SELECT name, elo_rating, games_played, last_played_at FROM models ORDER BY elo_rating DESC LIMIT 10;"
```

### Check if specific game was persisted
```bash
# Replace GAME_ID with actual game ID
sqlite3 llmsnake.db "SELECT * FROM games WHERE id = 'GAME_ID';"
sqlite3 llmsnake.db "SELECT * FROM game_participants WHERE game_id = 'GAME_ID';"
```

### Verify incremental vs batch ELO match
```bash
# Get current DB ratings
sqlite3 llmsnake.db "SELECT name, elo_rating FROM models ORDER BY name;" > db_elo.txt

# Recompute from scratch using elo_tracker.py
python3 elo_tracker.py completed_games/ --output completed_games/

# Compare (check stats_simple.json for recomputed ELO)
```

---

## Common Issues

### "data_access module not available"
- Ensure `backend/data_access/` directory exists
- Check that `__init__.py`, `game_persistence.py`, and `model_updates.py` are present
- Verify Python can find the module (try `python3 -c "from data_access import insert_game"`)

### "Model 'X' not found in database"
- Run `python3 seed_models.py` to populate the models table
- Ensure the model name in `main.py` matches the name in the database exactly

### ELO not updating
- Check console output for "Successfully persisted game X to database"
- Look for any error messages in the persistence flow
- Verify the game exists in the `games` table
- Check that participants were inserted in `game_participants` table

### Database locked
- Close any open sqlite3 connections
- Check for other processes accessing the database
- Restart the backend if needed

---

## Performance Monitoring

### Check database size
```bash
ls -lh backend/llmsnake.db
```

### Count records
```bash
sqlite3 llmsnake.db "SELECT
  (SELECT COUNT(*) FROM models) as models,
  (SELECT COUNT(*) FROM games) as games,
  (SELECT COUNT(*) FROM game_participants) as participants;"
```

### Check for slow queries
```bash
sqlite3 llmsnake.db "EXPLAIN QUERY PLAN SELECT * FROM models ORDER BY elo_rating DESC LIMIT 10;"
```

---

## Rollback Instructions

If Phase 2 needs to be disabled:

1. **Comment out DB persistence in main.py:**
   ```python
   # game.persist_to_database()  # Disabled
   ```

2. **Game will continue to work with JSON files only**

3. **To rebuild database from JSON files later:**
   ```bash
   python3 import_historical_games.py
   python3 recompute_elo.py
   ```

---

## Next Steps

After Phase 2 is validated:
- Proceed to Phase 3: API Layer (DB-Backed)
- Implement `GET /api/models` endpoint
- Implement `GET /api/games` endpoint
- Update frontend to use new endpoints
