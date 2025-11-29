"""
Tests for video generator helpers.
"""

import sys
import types


# Provide a dummy supabase module so importing video_generator doesn't error if
# supabase isn't installed or env vars are missing.
fake_supabase = types.SimpleNamespace(create_client=lambda url, key: None, Client=object)
sys.modules.setdefault("supabase", fake_supabase)

from services.video_generator import SnakeVideoGenerator  # noqa: E402


def test_normalize_replay_accepts_new_schema():
    """_normalize_replay should accept the new frames-based schema."""
    generator = SnakeVideoGenerator(fps=1)

    new_replay = {
        "game": {
            "id": "game-123",
            "board": {"width": 10, "height": 10, "num_apples": 5}
        },
        "players": {
            "0": {"name": "Alpha"},
            "1": {"name": "Beta"}
        },
        "frames": [
            {
                "round": 0,
                "state": {
                    "snakes": {"0": [[0, 0]], "1": [[1, 1]]},
                    "apples": [],
                    "alive": {"0": True, "1": True},
                    "scores": {"0": 0, "1": 0}
                },
                "moves": {
                    "0": {"move": "UP"},
                    "1": {"move": "LEFT"}
                }
            }
        ]
    }

    metadata, rounds = generator._normalize_replay(new_replay)

    assert metadata["game_id"] == "game-123"
    assert metadata["models"] == {"0": "Alpha", "1": "Beta"}
    assert len(rounds) == 1
    assert rounds[0]["round_number"] == 0
    assert rounds[0]["move_history"][0]["0"]["move"] == "UP"
    assert rounds[0]["move_history"][0]["1"]["move"] == "LEFT"
