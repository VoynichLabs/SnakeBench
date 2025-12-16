#!/usr/bin/env python3
"""
Example usage of the Video Generator Service

This demonstrates various ways to use the video generation service
in your application workflow.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.video_generator import SnakeVideoGenerator, get_video_public_url


def _get_completed_games_dir() -> str:
    d = os.getenv("SNAKEBENCH_COMPLETED_GAMES_DIR", "completed_games_local").strip()
    return d or "completed_games_local"


def example_1_generate_and_upload():
    """Example 1: Generate video and upload to Supabase in one step"""
    print("Example 1: Generate and Upload")
    print("-" * 50)

    game_id = "your-game-id-here"
    generator = SnakeVideoGenerator()

    # This will:
    # 1. Download replay from Supabase
    # 2. Generate video
    # 3. Upload to Supabase at {game_id}/replay.mp4
    # 4. Clean up temp files
    result = generator.generate_and_upload(game_id)

    print("Video uploaded!")
    print(f"  URL: {result['public_url']}")
    print()


def example_2_local_replay():
    """Example 2: Generate from local replay file"""
    print("Example 2: Local Replay File")
    print("-" * 50)

    import json

    # Load local replay
    replay_path = os.path.join(_get_completed_games_dir(), "snake_game_xyz.json")
    with open(replay_path, 'r') as f:
        replay_data = json.load(f)

    game_id = "xyz-game-id"
    generator = SnakeVideoGenerator()

    # Generate video without uploading
    video_path = generator.generate_video(
        game_id=game_id,
        replay_data=replay_data,
        output_path="./my_video.mp4"
    )

    print(f"Video saved to: {video_path}")
    print()


def example_3_custom_settings():
    """Example 3: Custom video settings"""
    print("Example 3: Custom Settings")
    print("-" * 50)

    # High quality, 4K resolution, 4 FPS
    generator = SnakeVideoGenerator(
        width=3840,
        height=2160,
        fps=4,
        cell_size=60
    )

    result = generator.generate_and_upload("game-id")
    print(f"High-quality video: {result['public_url']}")
    print()


def example_4_batch_processing():
    """Example 4: Batch process multiple games"""
    print("Example 4: Batch Processing")
    print("-" * 50)

    game_ids = [
        "game-id-1",
        "game-id-2",
        "game-id-3"
    ]

    generator = SnakeVideoGenerator()

    for game_id in game_ids:
        try:
            print(f"Processing {game_id}...")
            result = generator.generate_and_upload(game_id)
            print(f"  {result['public_url']}")
        except Exception as e:
            print(f"  Error: {e}")

    print()


def example_5_integration_with_game_completion():
    """Example 5: Integration with game completion workflow"""
    print("Example 5: Game Completion Integration")
    print("-" * 50)

    def on_game_complete(game_id: str, replay_data: dict):
        """
        Called when a game completes.
        Generates video asynchronously in the background.
        """
        print(f"Game {game_id} completed!")

        # Option A: Generate immediately (blocking)
        generator = SnakeVideoGenerator()
        result = generator.generate_and_upload(game_id)
        print(f"  Video ready: {result['public_url']}")

        # Option B: Queue for background processing (recommended)
        # queue_video_generation_task(game_id)

        return result['public_url']

    # Simulate game completion
    video_url = on_game_complete("test-game", {})
    print()


def example_6_get_video_url():
    """Example 6: Get video URL without checking if it exists"""
    print("Example 6: Get Video URL")
    print("-" * 50)

    game_id = "any-game-id"
    url = get_video_public_url(game_id)

    print(f"Video URL for {game_id}:")
    print(f"  {url}")
    print("\nNote: This doesn't check if the video actually exists!")
    print()


def example_7_error_handling():
    """Example 7: Proper error handling"""
    print("Example 7: Error Handling")
    print("-" * 50)

    generator = SnakeVideoGenerator()
    game_id = "some-game"

    try:
        result = generator.generate_and_upload(game_id)
        print(f"Success: {result['public_url']}")

    except ValueError as e:
        print(f"Invalid input: {e}")
        # Handle missing replay data

    except ConnectionError as e:
        print(f"Network error: {e}")
        # Handle Supabase connection issues

    except Exception as e:
        print(f"Unexpected error: {e}")
        # Log and alert

    print()


if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("Video Generator Service - Usage Examples")
    print("=" * 50 + "\n")

    # Run examples (commented out to avoid actual execution)
    # Uncomment the ones you want to try

    # example_1_generate_and_upload()
    # example_2_local_replay()
    # example_3_custom_settings()
    # example_4_batch_processing()
    # example_5_integration_with_game_completion()
    example_6_get_video_url()
    # example_7_error_handling()

    print("\n" + "=" * 50)
    print("For CLI usage, see: backend/cli/generate_video.py --help")
    print("=" * 50 + "\n")
