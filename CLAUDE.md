# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LLM Snake Arena is a competitive snake game simulation where different Large Language Models (LLMs) control snakes and compete against each other. The backend simulates games using Python, while the frontend displays leaderboards and game replays using Next.js.

### Core Architecture

**Backend (Python):**
- `main.py` - Core game simulation engine (SnakeGame class)
- `domain/` - Domain entities (Snake, GameState, constants)
- `players/` - Player implementations (LLMPlayer, RandomPlayer)
- `llm_providers.py` - Provider abstractions (OpenAI, Anthropic, Ollama, OpenRouter)
- `data_access/` - Database layer with repositories pattern
- `tasks.py` + `celery_app.py` - Distributed task execution via Celery/Redis
- `app.py` - Flask API server for frontend data

**Frontend (Next.js):**
- `src/app/` - Next.js 15 app router pages
- `src/components/` - React components organized by feature (home, match, layout)
- Server-side rendering with Tailwind CSS and Radix UI components

**Database:**
- PostgreSQL via Supabase (connection pooler on port 6543)
- Main tables: `models`, `games`, `game_participants`
- Elo ratings and model statistics tracked

## Common Development Commands

### Backend Development

```bash
cd backend

# Run a single game between two models
python3 main.py --models <model1> <model2>

# Example with specific models
python3 main.py --models gpt-4o-mini-2024-07-18 claude-3-haiku-20240307

# Customize game parameters
python3 main.py --models <model1> <model2> --width 30 --height 30 --max_rounds 200 --num_apples 8

# Ollama models (prefix with "ollama-")
python3 main.py --models ollama-llama3.2 ollama-llama3.3
```

### Distributed Game Execution (Celery)

```bash
cd backend

# Start Celery worker (requires Redis running)
celery -A celery_app worker --loglevel=info

# In another terminal, dispatch multiple games
python3 cli/dispatch_games.py --model_a <model1> --model_b <model2> --count 10 --monitor
```

### Database and ELO Management

```bash
cd backend

# Update Elo ratings from completed games
python3 cli/evaluate_models.py completed_games --output completed_games

# Sync OpenRouter models to database
python3 cli/sync_openrouter_models.py

# Generate matchups based on placement system
python3 cli/generate_matchups.py
```

### Video Generation

```bash
cd backend

# Generate video for a specific game
python3 cli/generate_video.py <game_id>

# Backfill videos for games without them
python3 cli/backfill_videos.py
```

### Testing

```bash
cd backend

# Run all tests
pytest

# Run specific test file
pytest tests/test_main.py

# Run with coverage
pytest --cov=. --cov-report=html
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Start development server (http://localhost:3000)
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Lint code
npm run lint
```

### API Server

```bash
cd backend

# Start Flask API server (default port 5000)
python3 app.py

# Or with gunicorn for production
gunicorn app:app
```

## Key Architectural Concepts

### Game Flow

1. **Initialization:** SnakeGame creates board, spawns snakes at random positions, places initial apples
2. **Round Loop:** Each round, all alive players get game state → LLM/Player decides move → moves are validated and applied → collisions detected → scores updated → state saved to history
3. **LLM Decision:** GameState serialized to text prompt → sent to LLM provider → response parsed for direction (UP/DOWN/LEFT/RIGHT) → fallback to random if invalid
4. **Game End:** Game ends when one snake remains, max rounds reached, or all snakes die
5. **Persistence:** Game saved as JSON to `backend/completed_games/` AND to PostgreSQL database

### Domain Model

**Snake** (`domain/snake.py`):
- Represented as `deque` of (x, y) positions
- Head at index 0, tail at end
- Moves by adding new head position and removing tail (unless growing)

**GameState** (`domain/game_state.py`):
- Immutable snapshot of game at specific round
- Contains: round number, all snake positions, alive status, scores, apple positions, move history
- `print_board()` returns ASCII representation (used in LLM prompts)

**Player Interface** (`players/base.py`):
- Abstract base: `get_move(game_state) -> dict`
- LLMPlayer: Calls LLM provider, parses response, tracks cost
- RandomPlayer: Returns random valid move (for testing)

### LLM Provider System

The `llm_providers.py` module provides a unified interface for multiple LLM providers:

- **OpenRouterProvider** - Primary provider, supports many models via OpenRouter API
- **AnthropicProvider** - Direct Anthropic API integration
- **OpenAIProvider** - Direct OpenAI API integration
- **OllamaProvider** - Local models via Ollama

Model configurations come from the Supabase `models` table with fields:
- `model_name` - API identifier (e.g., "gpt-4o-mini-2024-07-18")
- `provider` - Which provider to use ("openrouter", "anthropic", "openai", "ollama")
- `api_type` - API endpoint type ("completions" or "responses")
- `pricing_input` / `pricing_output` - Cost per million tokens
- `elo_rating` - Current skill rating

### Data Access Layer

Repository pattern separates database operations:

**Repositories** (`data_access/repositories/`):
- `base.py` - Base repository with connection management
- `model_repository.py` - Model CRUD operations
- `game_repository.py` - Game and participant operations

**High-Level Functions** (`data_access/`):
- `game_persistence.py` - Insert completed games and participants
- `model_updates.py` - Update model aggregates and ELO ratings
- `live_game.py` - Track in-progress games with round-by-round updates
- `api_queries.py` - Read-only queries for Flask API

### Celery Task System

Distributed game execution uses Celery with Redis:

1. `celery_app.py` - Celery application configuration
2. `tasks.py` - Task definitions (wraps `main.py:run_simulation()`)
3. `cli/dispatch_games.py` - Enqueues game tasks for workers to process

This allows horizontal scaling - run multiple workers to process games in parallel.

### Placement System

Confidence-weighted placement system (`placement_system.py`):

- New models start with initial ELO estimate and high uncertainty (sigma)
- System selects opponents to maximize information gain
- Game results weighted by decisiveness (score differential, death type)
- Handles "fluky" losses by allowing rematches
- Reduces uncertainty as more games are played

Key metrics from analysis:
- Top models: 8-10 apples/game
- Bottom models: 0.1-0.4 apples/game
- Wall deaths with low score = definitive skill gap
- Head collisions = essentially random

### Video Generation

The system can generate MP4 replays from game JSON files:

- `services/video_generator.py` - Renders frames using PIL, encodes with MoviePy/FFmpeg
- `services/supabase_storage.py` - Uploads videos to Supabase Storage
- Videos match frontend design: game canvas + player thoughts panels + scores
- Default: 2 FPS (500ms per frame)

### Frontend Architecture

**Pages:**
- `/` - Homepage with hero, stats, leaderboard
- `/match/[id]` - Game replay viewer with canvas animation
- `/models/[id]` - Individual model statistics
- `/live-games` - View currently running games
- `/about` - Project information

**Key Components:**
- `GameViewer` - Main replay component with canvas rendering
- `GameCanvas` - HTML5 canvas game board visualization
- `PlayerThoughts` - Displays LLM rationale for each move
- `LeaderboardSection` - Model rankings table

**State Management:**
- Client-side state with React hooks
- Server-side data fetching (Next.js server components)
- PostHog analytics integration

## Environment Configuration

Required environment variables (`.env` in `backend/`):

```bash
# LLM Provider API Keys
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
OPENROUTER_API_KEY=...

# OpenRouter headers (optional)
OPENROUTER_SITE_URL=https://snakebench.com
OPENROUTER_SITE_NAME=SnakeBench

# Supabase Database
SUPABASE_URL=https://[project-ref].supabase.co
SUPABASE_KEY=...
SUPABASE_DB_PASSWORD=...

# Redis (for Celery)
REDIS_URL=redis://localhost:6379/0

# Flask API
CORS_ALLOWED_ORIGINS=http://localhost:3000,https://snakebench.com

# Caching
TOP_MATCH_CACHE_SECONDS=900
```

Frontend environment variables (`.env.local` in `frontend/`):

```bash
NEXT_PUBLIC_API_URL=http://localhost:5000
NEXT_PUBLIC_POSTHOG_KEY=...
NEXT_PUBLIC_POSTHOG_HOST=...
```

## File Organization

### Game Output Files

All completed games are saved to `backend/completed_games/`:
- `snake_game_<uuid>.json` - Full game replay data
- `game_index.json` - Index of all completed games

Each game JSON contains:
- `game_id` - Unique identifier
- `metadata` - Players, timestamps, costs, board dimensions
- `initial_state` - Starting positions
- `replay_frames` - Frame-by-frame game state
- `player_thoughts` - LLM rationale for each move

### Database Schema

**models table:**
- Model metadata, API configuration, statistics, ELO rating
- Primary key: `id` (UUID)
- Unique: `model_slug` (URL-friendly identifier)

**games table:**
- Game metadata and results
- Primary key: `id` (UUID)
- Foreign keys to winning_model, losing_model

**game_participants table:**
- Links games to models with individual performance
- Composite key: (game_id, model_id)
- Stores: snake_number, score, alive, apples_eaten, etc.

## Important Notes

### Model Configuration

Models are now managed in the Supabase `models` table, not YAML files. To add new models:

1. Use `cli/sync_openrouter_models.py` to auto-discover OpenRouter models
2. Or insert directly into the `models` table
3. Set `is_active=true` to include in matchmaking

### Coordinate System

The game uses a coordinate system where (0,0) is at the **bottom-left** corner:
- x increases moving right
- y increases moving up
- This matches mathematical conventions but differs from typical array indexing

### Cost Tracking

LLM costs are tracked per-move and aggregated per-game:
- Pricing in dollars per million tokens
- Input tokens + output tokens calculated separately
- Total cost stored in game metadata

### Error Handling

LLM players have multiple fallback mechanisms:
1. Parse response for last valid direction mentioned
2. If invalid, generate random valid move and continue
3. Provider errors caught and logged, game continues with random move

This ensures games complete even with LLM failures.

### Phaser Renderer (Deprecated)

There's a separate `phaser-renderer/` directory for Puppeteer+Phaser+FFmpeg video generation, but the newer PIL-based `video_generator.py` is preferred. See `phaser-renderer/README.md` if needed.


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