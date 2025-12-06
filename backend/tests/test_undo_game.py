"""
Tests for undo_game CLI behavior switches.

These tests mock out DB-heavy functions to ensure the control flow chooses
the fast path by default and only runs the full replay when requested.
"""

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cli.undo_game as undo_game  # noqa: E402


def run_main(monkeypatch, argv, calls):
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(undo_game, "load_dotenv", lambda: None)
    monkeypatch.setattr(undo_game, "game_exists", lambda gid: True)
    monkeypatch.setattr(
        undo_game,
        "delete_game_and_participants",
        lambda gid: calls.append(("delete", gid)),
    )
    monkeypatch.setattr(
        undo_game,
        "recompute_aggregates_all_models",
        lambda: calls.append(("recompute_aggregates", None)),
    )
    monkeypatch.setattr(
        undo_game,
        "reset_models_and_stats",
        lambda: calls.append(("reset", None)),
    )
    monkeypatch.setattr(
        undo_game,
        "replay_all_but_target",
        lambda gid: (calls.append(("replay", gid)) or []),
    )
    undo_game.main()


def test_fast_path_does_not_replay_all(monkeypatch):
    calls = []
    run_main(monkeypatch, ["undo_game.py", "abc"], calls)

    assert ("delete", "abc") in calls
    assert ("recompute_aggregates", None) in calls
    assert not any(call[0] == "reset" for call in calls)
    assert not any(call[0] == "replay" for call in calls)


def test_replay_all_flag_triggers_full_rebuild(monkeypatch):
    calls = []
    run_main(monkeypatch, ["undo_game.py", "--replay-all", "abc"], calls)

    assert ("replay", "abc") in calls
    assert ("delete", "abc") in calls
    assert not any(call[0] == "recompute_aggregates" for call in calls)


def test_dry_run_fast_path_makes_no_changes(monkeypatch):
    calls = []
    run_main(monkeypatch, ["undo_game.py", "--dry-run", "abc"], calls)

    assert not calls
