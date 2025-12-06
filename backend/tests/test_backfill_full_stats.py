"""
Tests for full backfill CLI control flow.

These tests mock DB interactions to ensure we reset, then process games, and honor flags.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cli.backfill_full_stats as backfill  # noqa: E402


def run_main(monkeypatch, argv, calls, stream_ids):
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(backfill, "load_dotenv", lambda: None)
    monkeypatch.setattr(backfill, "reset_models_to_baseline", lambda: calls.append("reset"))
    monkeypatch.setattr(
        backfill,
        "stream_game_ids",
        lambda **kwargs: iter(stream_ids),
    )
    monkeypatch.setattr(
        backfill,
        "update_model_aggregates",
        lambda gid: calls.append(("aggregates", gid)),
    )
    monkeypatch.setattr(
        backfill,
        "update_trueskill_ratings",
        lambda gid: calls.append(("trueskill", gid)),
    )
    backfill.main()


def test_default_runs_reset_and_updates(monkeypatch):
    calls = []
    run_main(monkeypatch, ["backfill_full_stats.py"], calls, ["g1", "g2"])

    assert "reset" in calls
    assert ("aggregates", "g1") in calls and ("trueskill", "g1") in calls
    assert ("aggregates", "g2") in calls and ("trueskill", "g2") in calls


def test_no_reset_skips_reset(monkeypatch):
    calls = []
    run_main(monkeypatch, ["backfill_full_stats.py", "--no-reset"], calls, [])
    assert "reset" not in calls


def test_dry_run_makes_no_updates(monkeypatch):
    calls = []
    run_main(monkeypatch, ["backfill_full_stats.py", "--dry-run"], calls, ["g1"])
    assert calls == [], "Dry-run should not invoke reset or updates"
