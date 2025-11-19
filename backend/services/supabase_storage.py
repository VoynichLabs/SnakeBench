"""
Supabase Storage helper for managing game replay files.

This module handles uploading and retrieving game replay data from
Supabase Storage, organized by game ID for easy future expansion
(videos, audio, etc.).
"""

import os
import json
import logging
import sys
from typing import Dict, Any, Optional

# Add backend directory to path for imports
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from services.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


def upload_replay(game_id: str, replay_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Upload a game replay JSON file to Supabase Storage.

    Structure: <bucket>/<game_id>/replay.json
    This allows for future expansion with videos, audio, etc. in the same folder.

    Args:
        game_id: Unique game identifier (UUID)
        replay_data: Dictionary containing the complete game replay data

    Returns:
        Dictionary with:
        - storage_path: The storage path (e.g., "abc-123/replay.json")
        - public_url: The full public URL to access the file

    Raises:
        ValueError: If bucket name is not configured
        Exception: If upload fails
    """
    bucket_name = os.getenv('SUPABASE_BUCKET')

    if not bucket_name:
        raise ValueError("SUPABASE_BUCKET environment variable is required")

    supabase = get_supabase_client()

    # Define the storage path: <game_id>/replay.json
    storage_path = f"{game_id}/replay.json"

    try:
        # Convert replay data to JSON bytes
        replay_json = json.dumps(replay_data, indent=2)
        replay_bytes = replay_json.encode('utf-8')

        # Upload to Supabase Storage
        result = supabase.storage.from_(bucket_name).upload(
            path=storage_path,
            file=replay_bytes,
            file_options={
                "content-type": "application/json",
                "upsert": "true"  # Allow overwriting if file exists
            }
        )

        # Construct the public URL
        supabase_url = os.getenv('SUPABASE_URL')
        public_url = f"{supabase_url}/storage/v1/object/public/{bucket_name}/{storage_path}"

        logger.info(f"Successfully uploaded replay for game {game_id} to {storage_path}")

        return {
            'storage_path': storage_path,
            'public_url': public_url
        }

    except Exception as e:
        logger.error(f"Failed to upload replay for game {game_id}: {e}")
        raise


def get_replay_public_url(game_id: str) -> str:
    """
    Construct the public URL for a game replay without checking if it exists.

    Args:
        game_id: Unique game identifier

    Returns:
        The public URL to access the replay file
    """
    bucket_name = os.getenv('SUPABASE_BUCKET', 'matches')
    supabase_url = os.getenv('SUPABASE_URL')

    if not supabase_url:
        raise ValueError("SUPABASE_URL environment variable is required")

    storage_path = f"{game_id}/replay.json"
    return f"{supabase_url}/storage/v1/object/public/{bucket_name}/{storage_path}"


def download_replay(game_id: str) -> Optional[Dict[str, Any]]:
    """
    Download and parse a game replay from Supabase Storage.

    Args:
        game_id: Unique game identifier

    Returns:
        Dictionary containing the replay data, or None if not found

    Raises:
        Exception: If download fails for reasons other than not found
    """
    bucket_name = os.getenv('SUPABASE_BUCKET')

    if not bucket_name:
        raise ValueError("SUPABASE_BUCKET environment variable is required")

    supabase = get_supabase_client()
    storage_path = f"{game_id}/replay.json"

    try:
        # Download the file
        response = supabase.storage.from_(bucket_name).download(storage_path)

        # Parse JSON
        replay_data = json.loads(response)
        logger.info(f"Successfully downloaded replay for game {game_id}")
        return replay_data

    except Exception as e:
        # Check if it's a "not found" error
        if "not found" in str(e).lower() or "404" in str(e):
            logger.warning(f"Replay not found for game {game_id}")
            return None

        logger.error(f"Failed to download replay for game {game_id}: {e}")
        raise


def delete_replay(game_id: str) -> bool:
    """
    Delete a game replay from Supabase Storage.

    Args:
        game_id: Unique game identifier

    Returns:
        True if deleted successfully, False otherwise
    """
    bucket_name = os.getenv('SUPABASE_BUCKET')

    if not bucket_name:
        raise ValueError("SUPABASE_BUCKET environment variable is required")

    supabase = get_supabase_client()
    storage_path = f"{game_id}/replay.json"

    try:
        supabase.storage.from_(bucket_name).remove([storage_path])
        logger.info(f"Successfully deleted replay for game {game_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to delete replay for game {game_id}: {e}")
        return False


def list_game_files(game_id: str) -> list:
    """
    List all files in a game's folder (replay.json, video.mp4, etc.).

    Args:
        game_id: Unique game identifier

    Returns:
        List of file metadata dictionaries
    """
    bucket_name = os.getenv('SUPABASE_BUCKET')

    if not bucket_name:
        raise ValueError("SUPABASE_BUCKET environment variable is required")

    supabase = get_supabase_client()

    try:
        files = supabase.storage.from_(bucket_name).list(path=game_id)
        logger.info(f"Listed {len(files)} files for game {game_id}")
        return files

    except Exception as e:
        logger.error(f"Failed to list files for game {game_id}: {e}")
        return []
