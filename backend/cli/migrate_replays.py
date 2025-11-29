#!/usr/bin/env python3
"""
One-off migration script to convert legacy replay JSON files (metadata + rounds)
into the new frames-based schema used by the frontend/video renderer.

Usage examples:
  # Migrate a single file and write alongside it with ".migrated.json"
  python migrate_replays.py --input ../completed_games/snake_game_abc.json

  # Migrate a directory of replays in-place (overwrites!)
  python migrate_replays.py --input ../completed_games --in-place

  # Migrate a directory to an output folder
  python migrate_replays.py --input ../completed_games --output ../migrated_replays
"""

import argparse
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple


def load_replay(path: Path) -> Dict[str, Any]:
    with path.open() as f:
        return json.load(f)


def extract_moves(round_data: Dict[str, Any]) -> Dict[str, Any]:
    """Get the per-round moves from legacy round.move_history (last entry only)."""
    move_history = round_data.get("move_history")
    if isinstance(move_history, list) and move_history:
        last_entry = move_history[-1]
        if isinstance(last_entry, dict):
            return last_entry
    return {}


def sum_tokens_and_cost(rounds: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Aggregate input/output tokens and cost per player from legacy rounds."""
    totals: Dict[str, Dict[str, Any]] = {}
    for rd in rounds:
        moves = extract_moves(rd)
        for sid, move in moves.items():
            player_totals = totals.setdefault(sid, {"input_tokens": 0, "output_tokens": 0, "cost": 0.0})
            player_totals["input_tokens"] += move.get("input_tokens", 0) or 0
            player_totals["output_tokens"] += move.get("output_tokens", 0) or 0
            player_totals["cost"] += move.get("cost", 0.0) or 0.0
    return totals


def build_frames(rounds: List[Dict[str, Any]], death_info: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Convert legacy rounds to frames and build an initial_state snapshot."""
    frames: List[Dict[str, Any]] = []
    initial_state = None

    for idx, rd in enumerate(rounds):
        round_number = rd.get("round_number", idx)
        state = {
            "snakes": rd.get("snake_positions", {}),
            "apples": rd.get("apples", []),
            "alive": rd.get("alive", {}),
            "scores": rd.get("scores", {}),
        }
        if initial_state is None:
            initial_state = state

        moves = extract_moves(rd)

        events = []
        for sid, info in death_info.items():
            if info and info.get("round") == round_number:
                events.append({"type": "death", "player_id": sid, "reason": info.get("reason")})

        frame = {
            "round": round_number,
            "state": state,
            "moves": moves or None
        }
        if events:
            frame["events"] = events

        frames.append(frame)

    if initial_state is None:
        initial_state = {"snakes": {}, "apples": [], "alive": {}, "scores": {}}

    return frames, initial_state


def migrate_replay(old_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert legacy replay dict to the new frames-based schema.

    If the file is already migrated but still carries legacy `metadata`,
    we strip it and return the cleaned payload.
    """
    if "frames" in old_data and "game" in old_data:
        cleaned = dict(old_data)
        cleaned.pop("metadata", None)
        return cleaned

    metadata = old_data.get("metadata", {})
    rounds = old_data.get("rounds", [])
    if not metadata or not rounds:
        raise ValueError("Replay missing metadata or rounds; cannot migrate.")

    death_info = metadata.get("death_info", {}) or {}
    models = metadata.get("models", {}) or {}

    board_width = rounds[0].get("width", 0)
    board_height = rounds[0].get("height", 0)
    board = {"width": board_width, "height": board_height}
    if "num_apples" in metadata:
        board["num_apples"] = metadata.get("num_apples")

    frames, initial_state = build_frames(rounds, death_info)
    player_totals = sum_tokens_and_cost(rounds)

    players = {}
    for sid, name in models.items():
        totals = player_totals.get(sid, {"input_tokens": 0, "output_tokens": 0, "cost": 0.0})
        # Override cost with metadata player_costs if present
        player_costs = metadata.get("player_costs", {})
        if sid in player_costs:
            totals = dict(totals)
            totals["cost"] = player_costs[sid]

        players[sid] = {
            "model_id": sid,
            "name": name,
            "result": metadata.get("game_result", {}).get(sid),
            "final_score": metadata.get("final_scores", {}).get(sid, 0),
            "death": death_info.get(sid),
            "totals": totals,
        }

    totals_payload = {
        "cost": metadata.get("total_cost") or sum(t.get("cost", 0.0) for t in player_totals.values()),
        "input_tokens": sum(t.get("input_tokens", 0) for t in player_totals.values()),
        "output_tokens": sum(t.get("output_tokens", 0) for t in player_totals.values()),
    }

    game_payload = {
        "id": metadata.get("game_id", ""),
        "started_at": metadata.get("start_time"),
        "ended_at": metadata.get("end_time"),
        "game_type": metadata.get("game_type", "ladder"),
        "max_rounds": metadata.get("max_rounds"),
        "rounds_played": metadata.get("actual_rounds"),
        "board": board,
    }

    return {
        "version": 1,
        "game": game_payload,
        "players": players,
        "totals": totals_payload,
        "initial_state": initial_state,
        "frames": frames
    }


def write_replay(path: Path, data: Dict[str, Any]):
    with path.open("w") as f:
        json.dump(data, f, indent=2)


def migrate_file(path: Path, out_dir: Path, in_place: bool) -> Tuple[Path, bool, str]:
    try:
        data = load_replay(path)
        new_data = migrate_replay(data)

        if in_place:
            out_path = path
        else:
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / path.name.replace(".json", ".migrated.json")

        write_replay(out_path, new_data)
        return out_path, True, ""
    except Exception as exc:  # noqa: BLE001
        return path, False, str(exc)


def find_json_files(root: Path) -> List[Path]:
    if root.is_file():
        return [root] if root.suffix == ".json" else []
    return [p for p in root.rglob("*.json") if p.is_file()]


def main():
    parser = argparse.ArgumentParser(description="Migrate legacy replays to the new frames-based schema.")
    parser.add_argument("--input", required=True, help="Path to a replay JSON or a directory of replays.")
    parser.add_argument("--output", help="Output directory for migrated files (default: alongside input with .migrated.json).")
    parser.add_argument("--in-place", action="store_true", help="Overwrite the original files.")
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.output) if args.output else (input_path if input_path.is_dir() else input_path.parent)

    if args.in_place and args.output:
        raise ValueError("Use either --in-place or --output, not both.")

    files = find_json_files(input_path)
    if not files:
        print(f"No JSON files found under {input_path}")
        return

    successes = 0
    for f in files:
        out_path, ok, err = migrate_file(f, out_dir, args.in_place)
        if ok:
            successes += 1
            print(f"✓ Migrated {f} -> {out_path}")
        else:
            print(f"✗ Failed {f}: {err}")

    print(f"\nDone. Migrated {successes}/{len(files)} file(s).")


if __name__ == "__main__":
    main()
