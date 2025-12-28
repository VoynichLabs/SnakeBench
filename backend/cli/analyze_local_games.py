#!/usr/bin/env python3
"""
Author: Gemini 3 Flash High
Date: 2025-12-27
PURPOSE: Analyze local SnakeBench completed game replays to find "most interesting" games.
         Scans completed_games and completed_games_local for snake_game_*.json.
         Extracts metrics: cost, rounds, scores, duration, models, and winner.
         Supports CSV and Markdown reporting with date filtering (--since).
SRP/DRY check: Pass - encapsulated local analysis logic independent of DB.
"""

import argparse
import csv
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


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
    models: List[str]
    winner_name: str
    player_scores: Dict[str, int]
    started_at: Optional[datetime] = None


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

    # Scores and Models
    max_final_score = 0
    sum_final_scores = 0
    model_names = []
    player_scores = {}
    
    # Determine winner
    winner_id = str(game.get("winner_id")) if game.get("winner_id") is not None else None
    winner_name = "None"

    # Some games might have a winner stored in the player object itself
    winning_player = None
    for pid, p in players.items():
        if p.get("result") == "won":
            winning_player = p.get("name") or f"Player {pid}"
            break

    for pid, p in players.items():
        name = p.get("name") or f"Player {pid}"
        model_names.append(name)
        
        try:
            s = int(p.get("final_score") or 0)
        except (TypeError, ValueError):
            s = 0
        
        player_scores[name] = s
        if s > max_final_score:
            max_final_score = s
        sum_final_scores += s
        
        if str(pid) == winner_id:
            winner_name = name

    # Fallback for winner name if winner_id didn't match or was missing
    if winner_name == "None" and winning_player:
        winner_name = winning_player

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
        models=model_names,
        winner_name=winner_name,
        player_scores=player_scores,
        started_at=started_at
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze local SnakeBench completed game replays for interesting metrics",
    )
    parser.add_argument(
        "--root",
        type=str,
        action="append",
        help="Directory containing snake_game_*.json. Can be specified multiple times.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="How many top games to show per metric (default: 10)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Path to save the report (e.g., report.csv or report.md)",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["csv", "md"],
        default="csv",
        help="Output format (default: csv)",
    )
    parser.add_argument(
        "--since",
        type=str,
        help="Only include games played on or after this date (YYYY-MM-DD)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

    since_date = None
    if args.since:
        try:
            since_date = datetime.strptime(args.since, "%Y-%m-%d")
        except ValueError:
            raise SystemExit(f"Invalid date format for --since: {args.since}. Use YYYY-MM-DD.")

    roots = args.root
    if not roots:
        # Default to both standard folders
        backend_dir = Path(__file__).resolve().parent.parent
        roots = [
            str(backend_dir / "completed_games"),
            str(backend_dir / "completed_games_local")
        ]

    json_paths = []
    for r_str in roots:
        r_path = Path(r_str).resolve()
        if r_path.exists() and r_path.is_dir():
            json_paths.extend(sorted(r_path.glob("snake_game_*.json")))
        else:
            logger.warning("Directory does not exist or is not a directory: %s", r_path)

    if not json_paths:
        logger.info("No snake_game_*.json files found.")
        return

    logger.info("Analyzing %d local games across %d directories", len(json_paths), len(roots))

    games: List[GameMetrics] = []
    for p in json_paths:
        m = extract_metrics(p)
        if m is not None:
            if since_date and (not m.started_at or m.started_at < since_date):
                continue
            games.append(m)

    if not games:
        logger.info("No valid games found matching filters.")
        return

    logger.info("Analyzing %d local games", len(games))

    top_n = max(1, args.top)

    report_lines = []
    report_lines.append("# SnakeBench Local Game Analysis Report")
    report_lines.append(f"Analyzed {len(json_paths)} games")
    report_lines.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")

    def show(title: str, items: List[GameMetrics], key_desc: str):
        logger.info("")
        logger.info("=== %s (top %d by %s) ===", title, top_n, key_desc)
        
        report_lines.append(f"## {title}")
        report_lines.append(f"Top {top_n} by {key_desc}:")
        report_lines.append("")
        report_lines.append("| Game ID | File | Models | Winner | Rounds | Max Score | Sum Scores | Cost | Duration |")
        report_lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        
        for g in items[:top_n]:
            models_str = "; ".join(g.models)
            logger.info(
                "%s  winner=%-15s models=%-30s rounds=%d/%d  score_max=%d  cost=$%.4f",
                g.game_id,
                g.winner_name,
                models_str,
                g.rounds_played,
                g.max_rounds,
                g.max_final_score,
                g.total_cost,
            )
            report_lines.append(
                f"| `{g.game_id}` | `{g.filename}` | {models_str} | {g.winner_name} | {g.rounds_played}/{g.max_rounds} | {g.max_final_score} | {g.sum_final_scores} | ${g.total_cost:.4f} | {g.duration_seconds:.1f}s |"
            )
        report_lines.append("")

    games_by_cost = sorted(games, key=lambda g: g.total_cost, reverse=True)
    games_by_rounds = sorted(games, key=lambda g: g.rounds_played, reverse=True)
    games_by_apples = sorted(games, key=lambda g: g.max_final_score, reverse=True)
    games_by_duration = sorted(games, key=lambda g: g.duration_seconds, reverse=True)

    # Specific thresholds requested by user
    pro_games = sorted([g for g in games if g.max_final_score >= 25], key=lambda g: g.max_final_score, reverse=True)
    worst_games = sorted([g for g in games if g.max_final_score <= 1], key=lambda g: g.max_final_score)

    show("Most Expensive Games", games_by_cost, "total_cost")
    show("Longest Games (Rounds)", games_by_rounds, "rounds_played")
    show("Highest-Scoring Games (Max Apples)", games_by_apples, "max_final_score")
    show("Longest Duration Games", games_by_duration, "duration_seconds")

    # New sections for specific apple counts
    show("Pro Matches (>= 25 apples)", pro_games, "max_final_score")
    show("Worst Matches (<= 1 apple)", worst_games, "max_final_score")

    if args.output:
        output_path = Path(args.output).resolve()
        
        if args.format == "csv":
            headers = [
                "game_id", "filename", "models", "winner", "rounds", "max_rounds",
                "max_score", "sum_scores", "total_cost", "duration_seconds", "started_at"
            ]
            with output_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                for g in games:
                    writer.writerow({
                        "game_id": g.game_id,
                        "filename": g.filename,
                        "models": "; ".join(g.models),
                        "winner": g.winner_name,
                        "rounds": g.rounds_played,
                        "max_rounds": g.max_rounds,
                        "max_score": g.max_final_score,
                        "sum_scores": g.sum_final_scores,
                        "total_cost": f"{g.total_cost:.4f}",
                        "duration_seconds": f"{g.duration_seconds:.1f}",
                        "started_at": g.started_at.isoformat() if g.started_at else ""
                    })
            logger.info("")
            logger.info("CSV report saved to %s", output_path)
            
        else: # Markdown
            with output_path.open("w", encoding="utf-8") as f:
                f.write("\n".join(report_lines))
            logger.info("")
            logger.info("Markdown report saved to %s", output_path)


if __name__ == "__main__":
    main()
