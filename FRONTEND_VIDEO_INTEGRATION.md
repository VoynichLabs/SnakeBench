# Frontend Video Integration

Video generation has been integrated into the match page! Users can now generate and download MP4 videos of game replays on-demand.

## How It Works

1. **User visits match page** → Button shows "Generate Video"
2. **User clicks button** → Backend generates video (2-5 seconds)
3. **Video ready** → Button changes to "Download Video"
4. **Future visits** → Video is already available for instant download

## User Flow

```
┌─────────────────────────────────────────────┐
│         Match Page Loaded                   │
│  ┌───────────────────────────────────────┐ │
│  │     Checking for video...             │ │
│  └───────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
                    ↓
        ┌───────────┴───────────┐
        │                       │
    ✓ Exists              ✗ Not Generated
        │                       │
        ↓                       ↓
┌───────────────┐     ┌──────────────────┐
│ Download Video│     │  Generate Video  │
│   (Green)     │     │   (Outline)      │
└───────────────┘     └──────────────────┘
                              │
                              ↓ (User clicks)
                      ┌──────────────────┐
                      │  Generating...   │
                      │   (Loading)      │
                      └──────────────────┘
                              │
                              ↓ (2-5 seconds)
                      ┌──────────────────┐
                      │ Download Video   │
                      │   (Green ✓)      │
                      └──────────────────┘
```

## Files Modified/Added

### Backend
- ✅ `backend/app.py` - Added 2 new endpoints:
  - `POST /api/matches/<match_id>/video` - Generate video
  - `GET /api/matches/<match_id>/video` - Check if video exists

### Frontend
- ✅ `frontend/src/components/match/VideoDownloadButton.tsx` - New component
- ✅ `frontend/src/components/match/MatchInfo.tsx` - Added button
- ✅ `frontend/src/app/match/[id]/page.tsx` - Pass matchId prop

## API Endpoints

### Generate Video
```http
POST /api/matches/{match_id}/video
```

**Response (Success):**
```json
{
  "success": true,
  "video_url": "https://...supabase.co/storage/.../replay.mp4",
  "storage_path": "{match_id}/replay.mp4",
  "match_id": "abc-123"
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "Match not found or replay unavailable"
}
```

### Check Video Status
```http
GET /api/matches/{match_id}/video
```

**Response:**
```json
{
  "exists": true,
  "video_url": "https://...supabase.co/storage/.../replay.mp4",
  "match_id": "abc-123"
}
```

## Component: VideoDownloadButton

### Props
```typescript
interface VideoDownloadButtonProps {
  matchId: string;
}
```

### States
- `checking` - Checking if video exists
- `not_generated` - Video doesn't exist yet
- `generating` - Currently generating video
- `available` - Video ready for download
- `error` - Generation failed

### Button States

| State | Button Text | Icon | Color | Clickable |
|-------|-------------|------|-------|-----------|
| `checking` | "Checking..." | Spinner | Outline | No |
| `not_generated` | "Generate Video" | Video | Outline | Yes |
| `generating` | "Generating Video..." | Spinner | Outline | No |
| `available` | "Download Video" | Download | Green | Yes |
| `error` | "Retry Video Generation" | Video | Outline | Yes |

## Environment Variables

Frontend needs:
```env
NEXT_PUBLIC_API_URL=http://localhost:5001
```

Backend uses existing:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-key
SUPABASE_BUCKET=matches
```

## Testing

### 1. Test with existing video
```bash
# Generate video via CLI first
cd backend
python -m cli.generate_video 00259fc3-a949-45e9-a65c-304043c6ffb2

# Visit match page
# Should show "Download Video" immediately
```

### 2. Test generation flow
```bash
# Visit match page for a game without video
# Click "Generate Video"
# Wait 2-5 seconds
# Should show "Download Video" with green button
```

### 3. Test error handling
```bash
# Try with invalid match ID
# Should show error message and retry button
```

## Video Specifications

- **Format**: MP4 (H.264)
- **Resolution**: 1920x1080 (Full HD)
- **FPS**: 2 frames per second
- **Duration**: ~50 seconds per 100 rounds
- **File Size**: ~20-50 KB per 100 rounds
- **Generation Time**: 2-5 seconds typical

## Storage Location

Videos are stored in Supabase Storage:
```
supabase://matches/
└── {match_id}/
    ├── replay.json   (game data)
    └── replay.mp4    (video)
```

## User Experience

### First-time visitor (no video)
1. Page loads → "Checking..." (< 1 second)
2. Shows "Generate Video" button
3. User clicks → "Generating..." (2-5 seconds)
4. Shows "Download Video" ✅

### Returning visitor (video exists)
1. Page loads → "Checking..." (< 1 second)
2. Shows "Download Video" ✅
3. User clicks → Opens video in new tab

## Error Handling

### Network Errors
- Displays error message
- Shows "Retry" button
- Logs to console for debugging

### Match Not Found
- Returns 404 from backend
- Displays user-friendly error
- Option to retry

### Generation Timeout
- Backend handles with proper error response
- Frontend shows retry option

## Performance

- **Initial check**: < 1 second (HEAD request)
- **Generation**: 2-5 seconds (server-side)
- **Download**: Instant (direct from Supabase CDN)

## Future Enhancements

Possible improvements:
- [ ] Progress bar during generation
- [ ] Video preview/player inline
- [ ] Share video link
- [ ] Multiple quality options
- [ ] Batch generate all videos
- [ ] WebSocket for real-time progress

## Example Usage

### Visit a match page
```
https://your-site.com/match/00259fc3-a949-45e9-a65c-304043c6ffb2
```

You'll see:
1. Match title and info
2. **Video download button** ← NEW!
3. Live replay player
4. Game controls

## Development

### Run backend
```bash
cd backend
python app.py
```

### Run frontend
```bash
cd frontend
npm run dev
```

### Test the integration
1. Visit http://localhost:3000/match/{any-match-id}
2. Click "Generate Video"
3. Wait for generation
4. Click "Download Video"

---

**Status**: ✅ Complete and integrated
**User Impact**: Users can now download MP4 videos of any match
**Generation**: On-demand (only when requested)
