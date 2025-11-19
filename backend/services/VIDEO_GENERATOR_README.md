# Snake Game Video Generator Service

This service generates MP4 videos from Snake game replay JSON files and uploads them to Supabase Storage.

## Features

- **Server-side rendering**: Generates videos without requiring a browser
- **Matches frontend design**: Renders game board, snakes, apples, and player thoughts panels
- **Automatic upload**: Stores videos in Supabase Storage at `{game_id}/replay.mp4`
- **High quality**: Configurable resolution and frame rate
- **Efficient**: Uses PIL for rendering and FFmpeg for encoding

## Architecture

The service consists of two main components:

1. **`video_generator.py`**: Core service for rendering frames and creating videos
2. **`generate_video.py`**: CLI tool for generating videos from command line

## Installation

The required dependencies are already in `requirements.txt`:
- `pillow` - Image rendering
- `moviepy` - Video encoding
- `numpy` - Frame processing
- `supabase` - Storage upload

## Usage

### Command Line Interface

```bash
# Generate video from a game in Supabase
python backend/cli/generate_video.py <game_id>

# Generate from local replay file
python backend/cli/generate_video.py --local backend/completed_games/snake_game_xyz.json

# Custom output path (no upload)
python backend/cli/generate_video.py <game_id> --output ./my_video.mp4 --no-upload

# Custom video settings
python backend/cli/generate_video.py <game_id> --fps 4 --width 1920 --height 1080
```

### Python API

```python
from services.video_generator import SnakeVideoGenerator

# Create generator
generator = SnakeVideoGenerator(
    width=1920,
    height=1080,
    fps=2
)

# Generate and upload in one step
result = generator.generate_and_upload(game_id="abc-123")
print(f"Video URL: {result['public_url']}")

# Or generate locally first
video_path = generator.generate_video(
    game_id="abc-123",
    output_path="./my_video.mp4"
)
```

### Get Video URL

```python
from services.video_generator import get_video_public_url

# Get URL for a game's video (doesn't check if it exists)
url = get_video_public_url("abc-123")
# Returns: https://<project>.supabase.co/storage/v1/object/public/matches/abc-123/replay.mp4
```

## Video Layout

The generated video matches your frontend design:

```
┌────────────────────────────────────────────────────────────┐
│                                                            │
│  ┌──────────┐      ┌─────────────┐      ┌──────────┐     │
│  │          │      │             │      │          │     │
│  │ Player 1 │      │    Game     │      │ Player 2 │     │
│  │  Panel   │      │   Canvas    │      │  Panel   │     │
│  │          │      │             │      │          │     │
│  │  Score   │      │   Snakes    │      │  Score   │     │
│  │ Thoughts │      │   Apples    │      │ Thoughts │     │
│  │          │      │    Grid     │      │          │     │
│  └──────────┘      └─────────────┘      └──────────┘     │
│                                                            │
│              Round X / Total                               │
└────────────────────────────────────────────────────────────┘
```

## Rendering Details

### Colors (Matching Frontend)
- **Player 1**: Green (#4F7022) with blue panel border
- **Player 2**: Blue (#036C8E) with purple panel border
- **Apples**: Red (#EA2014)
- **Grid**: Light gray (#E5E7EB)
- **Background**: White (#FFFFFF)

### Snake Rendering
- Body segments rendered as filled squares
- Head rendered darker with white eyes
- Coordinate system matches frontend (y-axis flipped)

### Player Panels
- Model name in header
- Score and alive/dead status
- Up to 8 thought lines with text wrapping
- Color-coded borders matching player colors

## File Structure

```
backend/
├── services/
│   ├── video_generator.py          # Core video generation service
│   ├── VIDEO_GENERATOR_README.md   # This file
│   ├── supabase_storage.py         # Storage utilities
│   └── supabase_client.py          # Supabase client
├── cli/
│   └── generate_video.py           # CLI tool
└── completed_games/
    └── *.json                      # Replay files
```

## Supabase Storage Structure

Videos are stored in the same folder as replay JSON files:

```
matches/                              # Bucket name (from SUPABASE_BUCKET env var)
├── {game_id}/
│   ├── replay.json                   # Game replay data
│   └── replay.mp4                    # Generated video (NEW)
```

## Environment Variables

Required environment variables (should already be configured):

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-key
SUPABASE_BUCKET=matches
```

## Performance

- **Rendering speed**: ~10-20 frames/second (depends on CPU)
- **Video encoding**: Uses FFmpeg with h264 codec
- **Typical video**: 100 rounds = ~50 seconds at 2 FPS = ~1-2 MB file size

## Error Handling

The service includes robust error handling:
- Missing replay data → Downloads from Supabase
- Upload failures → Keeps local file
- Rendering errors → Detailed logging
- Cleanup → Removes temp files automatically

## Future Enhancements

Possible improvements:
- Add audio (background music, sound effects)
- Overlay statistics/charts
- Slow-motion for key moments
- Multiple quality options
- Batch processing for multiple games
- Progress bar during rendering

## Testing

```bash
# Test with a local replay file
python backend/cli/generate_video.py --local backend/completed_games/snake_game_<id>.json --no-upload

# Test full pipeline (generate + upload)
python backend/cli/generate_video.py <game_id>

# Verify upload
# Check Supabase Storage dashboard for: {game_id}/replay.mp4
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'PIL'"
```bash
cd backend
pip install -r requirements.txt
```

### "FFmpeg not found"
```bash
# macOS
brew install ffmpeg

# Linux
sudo apt-get install ffmpeg
```

### "SUPABASE_BUCKET environment variable is required"
Ensure your `.env` file has:
```
SUPABASE_BUCKET=matches
```

### Video quality issues
Adjust resolution and FPS:
```bash
python backend/cli/generate_video.py <game_id> --width 2560 --height 1440 --fps 4
```

## Integration Examples

### Add to game completion workflow

```python
from services.video_generator import SnakeVideoGenerator

# After game completes and replay is uploaded
def on_game_complete(game_id: str):
    # Generate video asynchronously
    generator = SnakeVideoGenerator()
    result = generator.generate_and_upload(game_id)

    # Store video URL in database
    update_game_record(game_id, video_url=result['public_url'])
```

### Batch process existing games

```python
import os
from services.video_generator import SnakeVideoGenerator

generator = SnakeVideoGenerator()

# Process all local replay files
replay_dir = "backend/completed_games"
for filename in os.listdir(replay_dir):
    if filename.endswith('.json') and filename != 'game_index.json':
        game_id = filename.replace('snake_game_', '').replace('.json', '')
        print(f"Processing {game_id}...")

        try:
            result = generator.generate_and_upload(game_id)
            print(f"  ✓ {result['public_url']}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
```

## API Reference

### `SnakeVideoGenerator`

**Constructor:**
```python
SnakeVideoGenerator(
    width: int = 1920,
    height: int = 1080,
    fps: int = 2,
    cell_size: int = 40
)
```

**Methods:**

- `generate_video(game_id, replay_data=None, output_path=None) -> str`
  - Generates video and returns local file path
  - Downloads replay from Supabase if `replay_data` is None

- `generate_and_upload(game_id) -> Dict[str, str]`
  - Generates video and uploads to Supabase
  - Returns `{'storage_path': str, 'public_url': str}`

### Helper Functions

- `get_video_public_url(game_id: str) -> str`
  - Constructs public URL for a game's video
  - Does not verify if video exists

- `hex_to_rgb(hex_color: str) -> Tuple[int, int, int]`
  - Converts hex color to RGB tuple

- `darken_color(hex_color: str, amount: float) -> Tuple[int, int, int]`
  - Darkens a color by specified amount
