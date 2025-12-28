#!/usr/bin/env python3
"""Analyze local SnakeBench completed game replays to find "most interesting" games.

This is a LOCAL-ONLY tool for the arc-explainer repo. It:
- Scans external/SnakeBench/backend/completed_games for snake_game_*.json.
- Extracts per-game metrics:
  - total_cost
  - rounds_played / max_rounds
  - per-player final_score (and their max / sum)
  - duration_seconds (ended_at - started_at)
- Prints top N games by each metric.

No Supabase or Postgres access is used; everything is computed from local JSON.
"""

import argparse
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


logger = logging.getLogger(__name__)


def _get_completed_games_dir() -> str:
    d = os.getenv("SNAKEBENCH_COMPLETED_GAMES_DIR", "completed_games_local").strip()
    return d or "completed_games_local"


@dataclass
class GameMetrics:
    game_id: str
    filename: str
    total_cost: float
    rounds_played: int
    max_rounds: int
    max_final_score: int
    sum_final_scores: int
    duration_seconds: float


def parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        # Timestamps look like "2025-12-11T02:51:32.618418"
        return datetime.fromisoformat(ts)
    except Exception:  # pragma: no cover - defensive
        return None


def extract_metrics(path: Path) -> Optional[GameMetrics]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to load %s: %s", path.name, exc)
        return None

    game = data.get("game", {}) or {}
    players: Dict[str, Dict] = data.get("players", {}) or {}
    totals = data.get("totals", {}) or {}

    game_id = str(game.get("id") or path.stem.replace("snake_game_", ""))

    # Rounds
    rounds_played = int(game.get("rounds_played") or 0)
    if not rounds_played:
        # Fallback: count frames/rounds arrays if present
        if isinstance(data.get("frames"), list):
            rounds_played = len(data["frames"])
        elif isinstance(data.get("rounds"), list):
            rounds_played = len(data["rounds"])

    max_rounds = int(game.get("max_rounds") or rounds_played or 0)

    # Cost: prefer totals.cost, fallback to sum of player totals
    total_cost = float(totals.get("cost") or 0.0)
    if not total_cost:
        c = 0.0
        for p in players.values():
            t = p.get("totals") or {}
            try:
                c += float(t.get("cost") or 0.0)
            except (TypeError, ValueError):
                continue
        total_cost = c

    # Scores
    max_final_score = 0
    sum_final_scores = 0
    for p in players.values():
        try:
            s = int(p.get("final_score") or 0)
        except (TypeError, ValueError):
            s = 0
        if s > max_final_score:
            max_final_score = s
        sum_final_scores += s

    # Duration
    started_at = parse_iso(game.get("started_at"))
    ended_at = parse_iso(game.get("ended_at"))
    if started_at and ended_at:
        duration_seconds = max(0.0, (ended_at - started_at).total_seconds())
    else:
        duration_seconds = 0.0

    return GameMetrics(
        game_id=game_id,
        filename=path.name,
        total_cost=total_cost,
        rounds_played=rounds_played,
        max_rounds=max_rounds,
        max_final_score=max_final_score,
        sum_final_scores=sum_final_scores,
        duration_seconds=duration_seconds,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze local SnakeBench completed game replays for interesting metrics",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=str(Path(__file__).resolve().parent.parent / _get_completed_games_dir()),
        help="Directory containing snake_game_*.json (default: ../completed_games)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="How many top games to show per metric (default: 10)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Root directory does not exist or is not a directory: {root}")

    json_paths = sorted(root.glob("snake_game_*.json"))
    if not json_paths:
        logger.info("No snake_game_*.json files found under %s", root)
        return

    logger.info("Analyzing %d local games under %s", len(json_paths), root)

    games: List[GameMetrics] = []
    for p in json_paths:
        m = extract_metrics(p)
        if m is not None:
            games.append(m)

    if not games:
        logger.info("No valid games parsed")
        return

    top_n = max(1, args.top)

    def show(title: str, items: List[GameMetrics], key_desc: str, key_fn):
        logger.info("")
        logger.info("=== %s (top %d by %s) ===", title, top_n, key_desc)
        for g in items[:top_n]:
            logger.info(
                "%s  file=%s  rounds=%d/%d  score_max=%d sum_scores=%d  cost=$%.4f  duration=%.1fs",
                g.game_id,
                g.filename,
                g.rounds_played,
                g.max_rounds,
                g.max_final_score,
                g.sum_final_scores,
                g.total_cost,
                g.duration_seconds,
            )

    games_by_cost = sorted(games, key=lambda g: g.total_cost, reverse=True)
    games_by_rounds = sorted(games, key=lambda g: g.rounds_played, reverse=True)
    games_by_apples = sorted(games, key=lambda g: g.max_final_score, reverse=True)
    games_by_duration = sorted(games, key=lambda g: g.duration_seconds, reverse=True)

    # Specific thresholds requested by user
    pro_games = sorted([g for g in games if g.max_final_score >= 25], key=lambda g: g.max_final_score, reverse=True)
    worst_games = sorted([g for g in games if g.max_final_score <= 1], key=lambda g: g.max_final_score)

    show("Most expensive games", games_by_cost, "total_cost", lambda g: g.total_cost)
    show("Longest games by rounds", games_by_rounds, "rounds_played", lambda g: g.rounds_played)
    show("Highest-scoring games (max apples)", games_by_apples, "max_final_score", lambda g: g.max_final_score)
    show("Longest duration games", games_by_duration, "duration_seconds", lambda g: g.duration_seconds)

    # New sections for specific apple counts
    show(f"Pro Matches (>25 apples)", pro_games, "max_final_score", lambda g: g.max_final_score)
    show(f"Worst Matches (<=1 apple)", worst_games, "max_final_score", lambda g: g.max_final_score)


if __name__ == "__main__":
    main()
