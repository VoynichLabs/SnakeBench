# Video Generation - Quick Start

## 🎬 Generate a Video in 3 Seconds

```bash
cd backend
python -m cli.generate_video <game_id>
```

That's it! The video will be:
1. Generated from the replay in Supabase
2. Uploaded to Supabase Storage at `{game_id}/replay.mp4`
3. Accessible at: `https://your-project.supabase.co/storage/v1/object/public/matches/{game_id}/replay.mp4`

---

## Common Commands

### Generate from Supabase (full pipeline)
```bash
python -m cli.generate_video abc-123-def-456
```

### Generate from local file
```bash
python -m cli.generate_video --local completed_games/snake_game_xyz.json
```

### Generate without uploading
```bash
python -m cli.generate_video abc-123 --no-upload --output ./my_video.mp4
```

### Custom quality
```bash
# 4K high quality
python -m cli.generate_video abc-123 --width 3840 --height 2160 --fps 4

# Fast preview
python -m cli.generate_video abc-123 --width 1280 --height 720 --fps 1
```

### Batch process all local files
```bash
./generate_videos.sh --batch
```

---

## Python API

```python
from services.video_generator import SnakeVideoGenerator

# One-liner
generator = SnakeVideoGenerator()
result = generator.generate_and_upload("game-id")
print(result['public_url'])
```

---

## What Gets Generated

### Video Layout
```
┌──────────────────────────────────────────┐
│  [Player 1]  [Game Board]  [Player 2]   │
│   Panel        Canvas         Panel      │
│                                          │
│  • Score      • Snakes      • Score     │
│  • Status     • Apples      • Status    │
│  • Thoughts   • Grid        • Thoughts  │
│                                          │
│            Round X / Total               │
└──────────────────────────────────────────┘
```

### Storage
```
supabase://matches/
└── {game_id}/
    ├── replay.json  ✓ (existing)
    └── replay.mp4   ✓ (new!)
```

---

## Testing

✅ **Verified working!**

Example video: https://ohcwbelgdvjxleimagqp.supabase.co/storage/v1/object/public/matches/00259fc3-a949-45e9-a65c-304043c6ffb2/replay.mp4

---

## Help

```bash
python -m cli.generate_video --help
```

For detailed documentation, see:
- `VIDEO_GENERATION.md` - Complete guide
- `services/VIDEO_GENERATOR_README.md` - API reference
- `examples/generate_video_example.py` - Code examples
