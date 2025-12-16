#!/usr/bin/env python3
"""
CLI tool to generate videos from Snake game replays

Usage:
    python generate_video.py <game_id>
    python generate_video.py --local <path_to_replay.json>

Examples:
    # Generate from local completed_games directory
    python generate_video.py abc-123-def-456

    # Generate from specific local file
    python generate_video.py --local ../completed_games/snake_game_xyz.json

    # Custom output path
    python generate_video.py abc-123 --output ./my_video.mp4

    # Custom video settings
    python generate_video.py abc-123 --fps 4 --width 1920 --height 1080
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from services.video_generator import SnakeVideoGenerator, get_video_local_path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_local_replay(file_path: str):
    """Load replay data from a local JSON file"""
    logger.info(f"Loading replay from local file: {file_path}")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Replay file not found: {file_path}")

    with open(file_path, 'r') as f:
        replay_data = json.load(f)

    logger.info(f"Loaded replay with {len(replay_data.get('rounds', []))} rounds")
    return replay_data


def extract_game_id_from_filename(file_path: str) -> str:
    """Extract game ID from filename"""
    # Expected format: snake_game_<game_id>.json
    filename = Path(file_path).stem
    if filename.startswith('snake_game_'):
        return filename.replace('snake_game_', '')
    return filename


def main():
    parser = argparse.ArgumentParser(
        description='Generate MP4 videos from Snake game replays',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        'game_id',
        nargs='?',
        help='Game ID to load from local replay directory'
    )
    input_group.add_argument(
        '--local',
        type=str,
        help='Path to local replay JSON file'
    )

    # Output options
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output video file path (default: local videos directory)'
    )

    # Video settings
    parser.add_argument(
        '--fps',
        type=int,
        default=2,
        help='Frames per second (default: 2)'
    )
    parser.add_argument(
        '--width',
        type=int,
        default=1920,
        help='Video width in pixels (default: 1920)'
    )
    parser.add_argument(
        '--height',
        type=int,
        default=1080,
        help='Video height in pixels (default: 1080)'
    )

    args = parser.parse_args()

    try:
        # Determine game ID and replay data
        if args.local:
            game_id = extract_game_id_from_filename(args.local)
            replay_data = load_local_replay(args.local)
            logger.info(f"Using game ID: {game_id}")
        else:
            game_id = args.game_id
            replay_data = None  # Will be loaded from local replay directory

        if not args.output:
            args.output = get_video_local_path(game_id)

        # Create video generator
        generator = SnakeVideoGenerator(
            width=args.width,
            height=args.height,
            fps=args.fps
        )

        # Generate video
        logger.info(f"Generating video for game {game_id}...")
        video_path = generator.generate_video(
            game_id=game_id,
            replay_data=replay_data,
            output_path=args.output
        )

        logger.info(f"[OK] Video generated successfully: {video_path}")
        logger.info("Done!")

    except KeyboardInterrupt:
        logger.info("\nCancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
