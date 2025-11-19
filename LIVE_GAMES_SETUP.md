# Live Games Feature - Setup & Testing Guide

## Quick Setup

### 1. Environment Configuration

Add to `frontend/.env`:
```bash
NEXT_PUBLIC_FLASK_URL=http://127.0.0.1:5000
```

### 2. Run Database Migration

```bash
cd backend
python run_migration.py
```

Expected output:
```
Running migration: add_live_game_support
✓ Added status column
✓ Added status check constraint
✓ Added current_state column
✓ Made replay_path nullable
✓ Created index on status
✓ Updated 0 existing games to 'completed' status

✅ Migration completed successfully!
```

### 3. Restart Services

**Backend** (Terminal 1):
```bash
cd backend
python app.py
```

**Frontend** (Terminal 2):
```bash
cd frontend
npm run dev
```

## Testing the Feature

### Start a Live Game

Terminal 3:
```bash
cd backend
python main.py --models "Google: Gemini 3 Pro Preview" "xAI: Grok 4 Fast" --max_rounds 30
```

Watch for these log messages:
```
Game ID: abc123...
Inserted initial game record abc123...
```

### View Live Games

1. **Navigate to Live Games List**:
   - Go to: http://localhost:3000/live-games
   - You should see a table with your running game
   - Red pulsing "LIVE" indicator
   - Current round updates every 2 seconds

2. **Watch a Specific Game**:
   - Click "Watch Live" button
   - See the ASCII board updating every 1 second
   - Real-time scores and snake positions
   - Auto-redirects to replay when complete

## What to Expect

### Live Games List View
- Polls backend every 2 seconds
- Shows all games with `status='in_progress'`
- Table columns:
  - Status (🔴 LIVE with animation)
  - Start Time
  - Current Round (updates live)
  - Board Size
  - Scores (Player 0: X | Player 1: Y)
  - Alive count (e.g., 2/2)
  - Watch Live button

### Live Game Viewer
- Polls backend every 1 second
- Shows ASCII board visualization
- Updates scores and positions in real-time
- Shows snake head positions and lengths
- Legend explaining board symbols
- When game completes:
  - Shows "Game completed!" message
  - Auto-redirects to `/match/[id]` after 3 seconds

## API Endpoints

Test them manually:

```bash
# Get all live games
curl http://127.0.0.1:5000/api/games/live

# Get specific game state
curl http://127.0.0.1:5000/api/games/{game-id}/live
```

## Common Issues & Solutions

### Issue: Frontend shows "undefined/api/games/live"
**Solution**: Add `NEXT_PUBLIC_FLASK_URL=http://127.0.0.1:5000` to `frontend/.env` and restart Next.js

### Issue: No live games showing
**Solution**:
1. Check Flask is running on port 5000
2. Verify game logs show "Inserted initial game record"
3. Check: `curl http://127.0.0.1:5000/api/games/live`

### Issue: Board not updating
**Solution**: Check backend logs for database connection errors

## How It Works

1. **Game Start**:
   ```
   SnakeGame.__init__()
   → insert_initial_game()
   → games table: status='in_progress'
   ```

2. **Each Round**:
   ```
   SnakeGame.run_round()
   → update_game_state()
   → games.current_state = {JSON with board, scores, etc}
   ```

3. **Game End**:
   ```
   SnakeGame.persist_to_database()
   → complete_game()
   → status='completed', current_state=NULL
   ```

4. **Frontend Polling**:
   ```
   /live-games: polls /api/games/live every 2s
   /live-games/[id]: polls /api/games/{id}/live every 1s
   ```

## File Locations

**Backend**:
- `backend/data_access/live_game.py` - Data access functions
- `backend/app.py` - API endpoints (lines 449-492)
- `backend/main.py` - Game integration (lines 365-377, 644-663, 764-778)

**Frontend**:
- `frontend/src/app/live-games/page.tsx` - List view
- `frontend/src/app/live-games/[id]/page.tsx` - Live viewer
- `frontend/src/components/layout/Navbar.tsx` - Navigation link

**Documentation**:
- `backend/LIVE_GAMES.md` - Full technical documentation

## Production Deployment

For production, update environment variables:

```bash
# frontend/.env.production
NEXT_PUBLIC_FLASK_URL=https://your-api-domain.com
```

The live game feature scales well because:
- Only `current_state` is stored (not full history)
- Efficient indexing on `status` column
- Polling at reasonable intervals (1-2 seconds)
- State cleared when game completes
