# Binary Search Placement System

## Overview

The LLMSnake evaluation system has been upgraded from an Elo-based opponent selection method to a **binary search placement algorithm**. This ensures that new models can efficiently find their correct position in the leaderboard with exactly 10 placement games.

## Key Benefits

1. **Guaranteed Convergence**: Perfect models (10 wins) will reach rank #0 (first place)
2. **Efficient Search**: Uses binary search to narrow down rank position in O(log N) games
3. **Fair Placement**: Models are placed based on their actual performance, not initial Elo estimates
4. **Predictable Results**: 10 games is mathematically sufficient for ~1024 models (2^10)

## How It Works

### Initial State
When a new model enters the system:
- `low = 0` (best possible rank)
- `high = N-1` (worst possible rank, where N = number of ranked models)
- Games to play: 10

### Opponent Selection
For each game, the system:
1. Calculates the midpoint: `target_index = (low + high) // 2`
2. Selects an opponent near that rank position
3. Prefers opponents not yet played against

### Interval Update After Each Game

**If the new model WINS:**
```
high = opponent_rank - 1
```
(They're at least as good as the opponent, so search above)

**If the new model LOSES:**
```
low = opponent_rank + 1
```
(They're below the opponent, so search below)

**If the game TIES:**
```
low = max(low, opponent_rank - 3)
high = min(high, opponent_rank + 3)
```
(Narrow the interval around the opponent)

### Example: Perfect Model (10 Wins)

Starting with 100 ranked models:

| Game | Opponent Rank | Result | New Interval | Interval Size |
|------|---------------|--------|--------------|---------------|
| 1    | 50            | Won    | [0, 49]      | 50            |
| 2    | 25            | Won    | [0, 24]      | 25            |
| 3    | 12            | Won    | [0, 11]      | 12            |
| 4    | 6             | Won    | [0, 5]       | 6             |
| 5    | 3             | Won    | [0, 2]       | 3             |
| 6    | 1             | Won    | [0, 0]       | 1             |

**Result**: Converged to rank #0 (first place) in 6 games!

### Example: Mid-Tier Model (Mixed Results)

| Game | Opponent Rank | Result | New Interval | Interval Size |
|------|---------------|--------|--------------|---------------|
| 1    | 50            | Won    | [0, 49]      | 50            |
| 2    | 25            | Lost   | [26, 49]     | 24            |
| 3    | 37            | Won    | [26, 36]     | 11            |
| 4    | 31            | Lost   | [32, 36]     | 5             |
| 5    | 34            | Won    | [32, 33]     | 2             |
| 6    | 32            | Lost   | [33, 33]     | 1             |

**Result**: Converged to rank #33 in 6 games!

## Implementation Details

### Files Modified

1. **`backend/placement_system.py`** (NEW)
   - Core binary search placement logic
   - State management for placement intervals
   - Opponent selection algorithms

2. **`backend/cli/run_evaluation_worker.py`** (MODIFIED)
   - Replaced `select_next_opponent()` with binary search version
   - Added placement state tracking
   - Shows convergence progress during evaluation

3. **`backend/migrations/add_placement_metadata.sql`** (NEW)
   - Adds `metadata` JSONB column to `evaluation_queue` table
   - Stores placement state between games

### Database Schema Changes

```sql
ALTER TABLE evaluation_queue
ADD COLUMN metadata JSONB;
```

This stores the placement state:
```json
{
  "model_id": 123,
  "low": 32,
  "high": 35,
  "games_played": 7,
  "max_games": 10,
  "opponents_played": [45, 67, 89, 23, 56, 34, 33]
}
```

## Usage

The binary search placement system is automatically used when evaluating new models:

```bash
# Queue a model for evaluation
python backend/cli/run_evaluation_worker.py --model "model-name"

# Run continuous evaluation worker
python backend/cli/run_evaluation_worker.py --continuous
```

### Example Output

```
--- Game 1/10 ---
Current search interval: ranks 0-299
Model X vs Model Y (Rank #150, ELO: 1520.00)
Result: WON | Score: 12-8
ELO: 1500.00 → 1516.00 (+16.00)
New search interval: ranks 0-149

--- Game 2/10 ---
Current search interval: ranks 0-149
Model X vs Model Z (Rank #75, ELO: 1580.00)
Result: LOST | Score: 6-14
ELO: 1516.00 → 1500.00 (-16.00)
New search interval: ranks 76-149

...

--- Game 6/10 ---
Current search interval: ranks 85-87
Model X vs Model A (Rank #86, ELO: 1505.00)
Result: WON | Score: 11-9
ELO: 1508.00 → 1512.00 (+4.00)
New search interval: ranks 85-85
✓ Placement converged to rank #85

======================================================================
Placement Complete!
======================================================================
Final rank position: #85
Placement interval: ranks 85-85
Games played: 10
======================================================================
```

## Testing

Run the test suite to verify the binary search algorithm:

```bash
python backend/test_placement.py
```

This runs 5 test scenarios:
1. Perfect model (wins all → rank #0)
2. Worst model (loses all → rank #99)
3. Mid-tier model (mixed results → rank ~33)
4. Unstable model (wins then loses)
5. Small pool (20 models)

All tests verify that the algorithm correctly converges to the appropriate rank.

## Comparison: Old vs New System

### Old System (Elo-based jumps)
- Started at median Elo
- Jumped by percentage (10-15%) based on wins/losses
- Could take many games to reach first place
- Jump sizes were arbitrary percentages

### New System (Binary search)
- Starts with full range [0, N-1]
- Uses binary search to halve search space
- Guaranteed to reach first place if winning all games
- Mathematically optimal convergence

## Mathematical Properties

- **Theoretical resolution**: 2^10 = 1024 models with 10 games
- **For 300 models**: log₂(300) ≈ 8.23 games needed theoretically
- **10 games provides**: 1-2 extra games for noise/ties
- **Convergence**: Typically converges in 6-8 games, uses remaining games for confirmation

## Edge Cases Handled

1. **No ranked models**: Places at rank 0
2. **Opponent outside interval**: Re-clamps to valid range
3. **All opponents played**: Allows replaying opponents
4. **Ties**: Narrows interval by ±3 ranks around opponent
5. **Interval collapse**: Stops searching when low = high

## Future Enhancements

Potential improvements:
1. **Confidence scoring**: Track uncertainty in final placement
2. **Adaptive margin**: Adjust tie margin based on game variance
3. **Multi-player support**: Extend to 3+ player games
4. **Re-calibration**: Periodic re-placement for established models
