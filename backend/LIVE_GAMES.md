# Live Game Tracking

This feature allows you to watch games as they happen in real-time by polling the API.

## How It Works

### Backend Flow

1. **Game Start**: When a game begins, an initial record is inserted into the `games` table with `status='in_progress'`
2. **Each Round**: After each round, the game's `current_state` JSON column is updated with the latest board state
3. **Game End**: When the game completes, `status` is set to `'completed'`, final stats are updated, and `current_state` is cleared

### Database Schema Changes

The `games` table now has:
- `status` column: `'queued' | 'in_progress' | 'completed' | 'failed'`
- `current_state` column: JSON text containing the current game state

The `current_state` JSON structure:
```json
{
  "round_number": 5,
  "snake_positions": {
    "0": [[3, 4], [3, 3], [3, 2]],
    "1": [[7, 8], [7, 7]]
  },
  "alive": {
    "0": true,
    "1": true
  },
  "scores": {
    "0": 2,
    "1": 1
  },
  "apples": [[5, 5], [2, 8], [9, 3]],
  "board_state": "9 . . . . . . . . . .\n8 . . A . . . . 1 . .\n..."
}
```

## API Endpoints

### 1. Get All Live Games
```
GET /api/games/live
```

**Response:**
```json
{
  "games": [
    {
      "id": "uuid-here",
      "status": "in_progress",
      "start_time": "2025-01-18T10:30:00",
      "rounds": 12,
      "board_width": 10,
      "board_height": 10,
      "num_apples": 5,
      "current_state": { ... }
    }
  ],
  "count": 1
}
```

### 2. Get Specific Game State
```
GET /api/games/<game_id>/live
```

**Response:**
```json
{
  "id": "uuid-here",
  "status": "in_progress",
  "start_time": "2025-01-18T10:30:00",
  "rounds": 12,
  "board_width": 10,
  "board_height": 10,
  "num_apples": 5,
  "current_state": {
    "round_number": 12,
    "snake_positions": { ... },
    "alive": { ... },
    "scores": { ... },
    "apples": [...],
    "board_state": "..."
  },
  "total_score": null,
  "total_cost": null
}
```

## Frontend Integration

### Pages Created

1. **Live Games List** (`/live-games`)
   - Displays all games with `status='in_progress'`
   - Polls every 2 seconds for updates
   - Shows round number, scores, alive count
   - Table format matching the models page design

2. **Live Game Viewer** (`/live-games/[id]`)
   - Shows real-time game board (ASCII visualization)
   - Displays current scores and snake positions
   - Polls every 1 second for updates
   - Auto-redirects to `/match/[id]` when game completes

3. **Navigation**
   - Added "🔴 Live Games" link to navbar
   - Positioned before "Top Match" for visibility

### Implementation Details

The frontend is built with:
- Next.js 14 App Router
- Client-side polling with React hooks
- Tailwind CSS for styling
- TypeScript for type safety

**Live Games List** (`frontend/src/app/live-games/page.tsx`):
```typescript
// Polls /api/games/live every 2 seconds
const fetchLiveGames = async () => {
  const response = await fetch(`${process.env.NEXT_PUBLIC_FLASK_URL}/api/games/live`);
  const data = await response.json();
  setLiveGames(data.games || []);
};

useEffect(() => {
  fetchLiveGames();
  const interval = setInterval(fetchLiveGames, 2000);
  return () => clearInterval(interval);
}, []);
```

**Live Game Viewer** (`frontend/src/app/live-games/[id]/page.tsx`):
```typescript
// Polls /api/games/{id}/live every 1 second
const fetchGameState = async (id: string) => {
  const response = await fetch(`${process.env.NEXT_PUBLIC_FLASK_URL}/api/games/${id}/live`);
  const data = await response.json();
  setGameState(data);

  // Auto-redirect when game completes
  if (data.status === 'completed') {
    setTimeout(() => router.push(`/match/${id}`), 3000);
  }
};

useEffect(() => {
  if (!gameId) return;
  fetchGameState(gameId);
  const interval = setInterval(() => fetchGameState(gameId), 1000);
  return () => clearInterval(interval);
}, [gameId]);
```

## Running a Test Game

```bash
# Run a game between two models
python main.py --models "Google: Gemini 3 Pro Preview" "xAI: Grok 4 Fast" --max_rounds 20

# In another terminal, poll for live games
curl http://localhost:5000/api/games/live

# Or watch a specific game
curl http://localhost:5000/api/games/<game-id>/live
```

## Performance Notes

- The `current_state` column is updated after each round (~0.3s delay between rounds)
- Frontend should poll at a reasonable rate (1-2 seconds) to avoid overwhelming the database
- When a game completes, `current_state` is set to NULL to save space
- An index on `games.status` makes live game queries fast even with many completed games

## Database Functions

New data access functions in `data_access/live_game.py`:

- `insert_initial_game()` - Create game record when starting
- `update_game_state()` - Update current state after each round
- `complete_game()` - Mark game as completed and clear current_state
- `get_live_games()` - Get all games with status='in_progress'
- `get_game_state()` - Get current state of a specific game

## Migration

Run the migration to add the new columns:

```bash
python run_migration.py
```

This adds:
- `status` column with check constraint
- `current_state` TEXT column
- Makes `replay_path` nullable
- Creates index on `status`
- Updates existing games to `status='completed'`

## Troubleshooting

### Frontend shows "undefined/api/games/live" in network requests

**Problem**: The environment variable `NEXT_PUBLIC_FLASK_URL` is not set.

**Solution**: Add to `frontend/.env`:
```bash
NEXT_PUBLIC_FLASK_URL=http://127.0.0.1:5000
```

Then restart your Next.js dev server:
```bash
npm run dev
```

**Note**: Environment variables prefixed with `NEXT_PUBLIC_` are exposed to the browser in Next.js. The pages have a fallback to `http://127.0.0.1:5000`, but it's better to set it explicitly.

### No live games showing even when a game is running

**Checklist**:
1. Check Flask server is running: `python app.py`
2. Check the game inserted initial record: Look for "Inserted initial game record" in logs
3. Query database directly:
   ```sql
   SELECT id, status, start_time, rounds
   FROM games
   WHERE status = 'in_progress'
   ORDER BY start_time DESC;
   ```
4. Check API endpoint manually: `curl http://127.0.0.1:5000/api/games/live`

### Live game viewer shows "Game Not Found"

**Possible causes**:
- Game already completed and status changed to 'completed'
- Invalid game ID in URL
- Database connection issue

**Debug**:
```bash
# Check if game exists
curl http://127.0.0.1:5000/api/games/{game-id}/live

# Check game status in database
SELECT id, status FROM games WHERE id = 'your-game-id';
```

### Game state not updating

**Possible causes**:
- Game crashed or stopped running
- Database connection lost
- `update_game_state()` failing silently

**Debug**: Check backend logs for warnings like "Could not update game state"
