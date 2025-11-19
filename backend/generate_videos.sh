#!/bin/bash
#
# Quick helper script for generating videos
#

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Snake Game Video Generator${NC}"
echo "================================"
echo ""

# Check if we're in the right directory
if [ ! -f "cli/generate_video.py" ]; then
    echo -e "${RED}Error: Must run from backend/ directory${NC}"
    exit 1
fi

# Parse command line arguments
if [ $# -eq 0 ]; then
    echo "Usage:"
    echo "  ./generate_videos.sh <game_id>              # Generate from Supabase"
    echo "  ./generate_videos.sh --local <file>         # Generate from local file"
    echo "  ./generate_videos.sh --batch                # Process all local files"
    echo "  ./generate_videos.sh --help                 # Show detailed help"
    exit 0
fi

if [ "$1" == "--help" ]; then
    python -m cli.generate_video --help
    exit 0
fi

if [ "$1" == "--batch" ]; then
    echo -e "${BLUE}Batch processing all local replay files...${NC}"
    echo ""

    count=0
    success=0
    failed=0

    for file in completed_games/snake_game_*.json; do
        if [ "$file" == "completed_games/snake_index.json" ]; then
            continue
        fi

        count=$((count + 1))
        filename=$(basename "$file")
        game_id=${filename#snake_game_}
        game_id=${game_id%.json}

        echo -e "${BLUE}[$count] Processing: ${game_id}${NC}"

        if python -m cli.generate_video --local "$file" 2>&1 | tail -1 | grep -q "Done!"; then
            success=$((success + 1))
            echo -e "${GREEN}  ✓ Success${NC}"
        else
            failed=$((failed + 1))
            echo -e "${RED}  ✗ Failed${NC}"
        fi
        echo ""
    done

    echo "================================"
    echo -e "${GREEN}Processed: $count games${NC}"
    echo -e "${GREEN}Success:   $success${NC}"
    echo -e "${RED}Failed:    $failed${NC}"
    exit 0
fi

# Single file processing
if [ "$1" == "--local" ]; then
    python -m cli.generate_video --local "$2" "${@:3}"
else
    python -m cli.generate_video "$@"
fi
