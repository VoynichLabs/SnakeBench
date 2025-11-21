"""
Undo a game: recompute ELO/aggregates excluding the game, then delete it.

This CLI performs a safe rollback for a mistakenly created game by:
- Recomputing all models' ELO ratings and aggregate stats from scratch,
  excluding the specified game id
- Updating the `models` table with the recomputed values
- Deleting the game's participants and the game record

Notes:
- Uses the same ELO logic as other parts of the system (K=32, pairwise expected score)
- Works against Supabase Postgres via `database_postgres.get_connection`
"""

import argparse
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Callable

from psycopg2.extras import RealDictCursor

from database_postgres import get_connection


# ELO parameters (must remain consistent with model_updates.py / elo_tracker.py)
K = 32
INITIAL_RATING = 1500.0
RESULT_RANK = {"won": 2, "tied": 1, "lost": 0}


def get_pair_result(result_i: str, result_j: str) -> Tuple[float, float]:
    """Return head-to-head score tuple (S_i, S_j) for two results."""
    rank_i = RESULT_RANK.get(result_i, 1)
    rank_j = RESULT_RANK.get(result_j, 1)
    if rank_i > rank_j:
        return 1.0, 0.0
    if rank_i < rank_j:
        return 0.0, 1.0
    return 0.5, 0.5


def expected_score(r_i: float, r_j: float) -> float:
    return 1.0 / (1.0 + 10 ** ((r_j - r_i) / 400.0))


def recompute_all_models_excluding(game_id_to_exclude: str) -> Tuple[Dict[int, float], Dict[int, Dict[str, int]], Dict[int, Optional[datetime]]]:
    """
    Recompute ELO ratings, aggregates, and last_played_at for all models,
    excluding a specific game id from the chronology.

    Returns:
      - ratings: model_id -> elo_rating
      - stats: model_id -> {wins, losses, ties, apples_eaten, games_played}
      - last_played_at: model_id -> latest end_time (or start_time) seen, or None
    """
    conn = get_connection()
    cursor: RealDictCursor = conn.cursor()

    # Order games chronologically, excluding the target
    cursor.execute(
        """
        SELECT id, start_time, end_time
        FROM games
        WHERE id <> %s
        ORDER BY start_time ASC NULLS FIRST
        """,
        (game_id_to_exclude,),
    )
    games = cursor.fetchall()

    ratings: Dict[int, float] = {}
    stats: Dict[int, Dict[str, int]] = {}
    last_played_at: Dict[int, Optional[datetime]] = defaultdict(lambda: None)

    def ensure_model(model_id: int):
        if model_id not in ratings:
            ratings[model_id] = INITIAL_RATING
        if model_id not in stats:
            stats[model_id] = {
                "wins": 0,
                "losses": 0,
                "ties": 0,
                "apples_eaten": 0,
                "games_played": 0,
            }

    try:
        for g in games:
            gid = g["id"]
            g_end = g.get("end_time")
            g_start = g.get("start_time")

            cursor.execute(
                """
                SELECT model_id, player_slot, score, result
                FROM game_participants
                WHERE game_id = %s
                ORDER BY player_slot
                """,
                (gid,),
            )
            parts = cursor.fetchall()
            if not parts:
                continue

            # Ensure all models exist in dicts
            for p in parts:
                ensure_model(p["model_id"])

            n = len(parts)
            # Accumulate pairwise actual and expected scores
            score_sum = {p["model_id"]: 0.0 for p in parts}
            expected_sum = {p["model_id"]: 0.0 for p in parts}

            for i in range(n):
                for j in range(i + 1, n):
                    pi = parts[i]
                    pj = parts[j]
                    mi = pi["model_id"]
                    mj = pj["model_id"]
                    s_i, s_j = get_pair_result(pi["result"], pj["result"])
                    e_i = expected_score(ratings[mi], ratings[mj])
                    e_j = expected_score(ratings[mj], ratings[mi])
                    score_sum[mi] += s_i
                    score_sum[mj] += s_j
                    expected_sum[mi] += e_i
                    expected_sum[mj] += e_j

            # Apply rating and stat updates
            for p in parts:
                mid = p["model_id"]
                if n > 1:
                    delta = (K / (n - 1)) * (score_sum[mid] - expected_sum[mid])
                    ratings[mid] += delta

                res = p["result"]
                if res == "won":
                    stats[mid]["wins"] += 1
                elif res == "lost":
                    stats[mid]["losses"] += 1
                else:
                    stats[mid]["ties"] += 1

                stats[mid]["apples_eaten"] += int(p["score"] or 0)
                stats[mid]["games_played"] += 1

                # Track last_played_at using end_time if present, else start_time
                ts: Optional[datetime] = g_end or g_start
                if ts is not None:
                    prev = last_played_at[mid]
                    if prev is None or ts > prev:
                        last_played_at[mid] = ts

        cursor.close()
        conn.close()
        return ratings, stats, last_played_at

    except Exception:
        cursor.close()
        conn.close()
        raise


def _fetch_game_participants(cur, game_id: str):
    cur.execute(
        """
        SELECT gp.model_id, m.name, gp.player_slot, gp.score, gp.result
        FROM game_participants gp
        JOIN models m ON m.id = gp.model_id
        WHERE gp.game_id = %s
        ORDER BY gp.player_slot
        """,
        (game_id,),
    )
    return cur.fetchall() or []


def _participants_only_recompute_elo(cur, game_id: str, participant_ids: List[int]) -> Dict[int, float]:
    """
    Recompute Elo for only the specified participant models, considering only
    their games (excluding the target game), while treating all opponents'
    ratings as fixed at their current DB values. Returns new Elo per participant.
    """
    # Get all games each participant was in (excluding this game), build union set
    game_rows: List[Dict] = []
    seen_game_ids = set()
    for mid in participant_ids:
        cur.execute(
            """
            SELECT g.id, g.start_time, g.end_time
            FROM games g
            JOIN game_participants gp ON gp.game_id = g.id
            WHERE gp.model_id = %s AND g.id <> %s
            ORDER BY g.start_time ASC NULLS FIRST
            """,
            (mid, game_id),
        )
        for r in cur.fetchall():
            gid = r["id"]
            if gid not in seen_game_ids:
                seen_game_ids.add(gid)
                game_rows.append(r)

    # Sort by start_time (None first) then id as tiebreaker
    game_rows.sort(key=lambda r: (r.get("start_time"), r["id"]))

    # Preload opponent current ratings for all models encountered across these games
    all_model_ids = set(participant_ids)
    for gr in game_rows:
        cur.execute(
            "SELECT model_id FROM game_participants WHERE game_id = %s",
            (gr["id"],),
        )
        all_model_ids.update([row["model_id"] for row in cur.fetchall()])

    # Use an IN clause with positional params for safety/compat
    id_list = list(all_model_ids)
    placeholders = ",".join(["%s"] * len(id_list))
    cur.execute(
        f"SELECT id, elo_rating FROM models WHERE id IN ({placeholders})",
        id_list,
    )
    current_elos = {row["id"]: float(row["elo_rating"]) for row in cur.fetchall()}

    # Working ratings: participants start from INITIAL, opponents fixed to current
    ratings: Dict[int, float] = {mid: INITIAL_RATING for mid in participant_ids}
    # Ensure opponents present in dict for lookup
    for mid, elo in current_elos.items():
        if mid not in ratings:
            ratings[mid] = elo

    # Process each game chronologically
    for gr in game_rows:
        gid = gr["id"]
        cur.execute(
            """
            SELECT model_id, result, score
            FROM game_participants
            WHERE game_id = %s
            ORDER BY player_slot
            """,
            (gid,),
        )
        parts = cur.fetchall()
        if not parts:
            continue
        n = len(parts)

        # Precompute sums for each participant we're updating (pairwise over all others)
        # We only update ratings for ids in participant_ids; others remain fixed
        score_sum = {p["model_id"]: 0.0 for p in parts if p["model_id"] in participant_ids}
        expected_sum = {p["model_id"]: 0.0 for p in parts if p["model_id"] in participant_ids}

        # Pairwise comparisons
        for i in range(n):
            for j in range(i + 1, n):
                mi = parts[i]["model_id"]
                mj = parts[j]["model_id"]
                s_i, s_j = get_pair_result(parts[i]["result"], parts[j]["result"])
                e_i = expected_score(ratings.get(mi, INITIAL_RATING), ratings.get(mj, INITIAL_RATING))
                e_j = expected_score(ratings.get(mj, INITIAL_RATING), ratings.get(mi, INITIAL_RATING))

                if mi in score_sum:
                    score_sum[mi] += s_i
                    expected_sum[mi] += e_i
                if mj in score_sum:
                    score_sum[mj] += s_j
                    expected_sum[mj] += e_j

        # Apply rating change only to our targets
        for pid in participant_ids:
            if pid in score_sum and n > 1:
                delta = (K / (n - 1)) * (score_sum[pid] - expected_sum[pid])
                ratings[pid] = ratings.get(pid, INITIAL_RATING) + delta

    # Return recomputed ratings for participants only
    return {mid: ratings[mid] for mid in participant_ids}


def _recompute_last_played_excluding(cur, model_id: int, game_id_to_exclude: str) -> Optional[datetime]:
    cur.execute(
        """
        SELECT MAX(COALESCE(g.end_time, g.start_time)) AS last_played
        FROM games g
        JOIN game_participants gp ON gp.game_id = g.id
        WHERE gp.model_id = %s AND g.id <> %s
        """,
        (model_id, game_id_to_exclude),
    )
    row = cur.fetchone()
    return row["last_played"] if row else None


def _delete_replay_asset(game_id: str, deleter: Optional[Callable[[str], bool]] = None) -> bool:
    """
    Best-effort deletion of the replay asset (e.g., Supabase storage).
    """
    if deleter is None:
        try:
            from services.supabase_storage import delete_replay  # type: ignore
        except Exception as exc:  # noqa: BLE001
            print(f"Skip replay deletion (cannot import storage helper): {exc}")
            return False
        deleter = delete_replay

    try:
        return bool(deleter(game_id))
    except Exception as exc:  # noqa: BLE001
        print(f"Replay deletion failed for {game_id}: {exc}")
        return False


def undo_game(
    game_id: str,
    dry_run: bool = False,
    scope: str = "participants",
    delete_replay: bool = False
) -> None:
    """
    Perform the undo operation for a given game id.

    Steps:
      1) Verify the game exists
      2) Recompute model ratings/stats excluding this game
      3) Update models accordingly (only ELO/aggregates/last_played_at)
      4) Delete participants and the game
    """
    conn = get_connection()
    cur: RealDictCursor = conn.cursor()

    # Ensure the game exists and collect a quick summary
    cur.execute("SELECT id, start_time, end_time FROM games WHERE id = %s", (game_id,))
    game_row = cur.fetchone()
    if not game_row:
        cur.close()
        conn.close()
        raise ValueError(f"Game '{game_id}' not found")

    # Gather participants for messaging and to ensure it has players
    participants = _fetch_game_participants(cur, game_id)
    if not participants:
        cur.close()
        conn.close()
        raise ValueError(f"Game '{game_id}' has no participants; aborting undo.")
    
    participant_ids = [p["model_id"] for p in participants]

    if scope not in ("participants", "global"):
        cur.close(); conn.close()
        raise ValueError("scope must be 'participants' or 'global'")

    if scope == "global":
        # Recompute ratings and stats excluding this game
        ratings, stats, last_played_map = recompute_all_models_excluding(game_id)

        # Fetch all models; we'll update all of them to ensure consistency
        cur.execute("SELECT id FROM models ORDER BY id")
        all_models = [row["id"] for row in cur.fetchall()]

        # Build parameter tuples for updates
        updates = []
        for mid in all_models:
            rating = ratings.get(mid, INITIAL_RATING)
            s = stats.get(mid, {
                "wins": 0,
                "losses": 0,
                "ties": 0,
                "apples_eaten": 0,
                "games_played": 0,
            })
            last_played = last_played_map.get(mid)
            updates.append((
                float(rating),
                int(s["wins"]),
                int(s["losses"]),
                int(s["ties"]),
                int(s["apples_eaten"]),
                int(s["games_played"]),
                last_played,  # may be None
                mid,
            ))
    else:
        # Participants-only recompute
        new_elos = _participants_only_recompute_elo(cur, game_id, participant_ids)

        # For aggregates, compute decrements from this game
        # and recompute last_played_at excluding this game
        updates = []
        for p in participants:
            mid = p["model_id"]
            # Fetch current aggregates
            cur.execute(
                "SELECT wins, losses, ties, apples_eaten, games_played FROM models WHERE id = %s",
                (mid,),
            )
            agg = cur.fetchone() or {"wins": 0, "losses": 0, "ties": 0, "apples_eaten": 0, "games_played": 0}

            # Decrement based on this game's result
            win_delta = 1 if p["result"] == "won" else 0
            loss_delta = 1 if p["result"] == "lost" else 0
            tie_delta = 1 if p["result"] == "tied" else 0
            apples_delta = int(p["score"] or 0)

            new_wins = max(0, int(agg["wins"]) - win_delta)
            new_losses = max(0, int(agg["losses"]) - loss_delta)
            new_ties = max(0, int(agg["ties"]) - tie_delta)
            new_apples = max(0, int(agg["apples_eaten"]) - apples_delta)
            new_games = max(0, int(agg["games_played"]) - 1)

            last_played = _recompute_last_played_excluding(cur, mid, game_id)

            updates.append((
                float(new_elos[mid]),
                new_wins,
                new_losses,
                new_ties,
                new_apples,
                new_games,
                last_played,
                mid,
            ))

    # Dry-run prints summary and exits
    if dry_run:
        print(f"Game {game_id} would be removed. Participants:")
        for p in participants:
            print(f"  - {p['name']} (id={p['model_id']}) result={p['result']} score={p['score']}")
        if scope == "global":
            print(f"Will update {len(all_models)} models and then delete game and participants.")
        else:
            # Show current vs recomputed ELO for each participant
            placeholders = ",".join(["%s"] * len(participant_ids))
            cur.execute(
                f"SELECT id, elo_rating FROM models WHERE id IN ({placeholders})",
                participant_ids,
            )
            current = {row["id"]: float(row["elo_rating"]) for row in cur.fetchall()}
            for p in participants:
                mid = p["model_id"]
                old = current.get(mid)
                new = new_elos.get(mid)
                if old is not None and new is not None:
                    print(f"  > {p['name']}: {old:.2f} -> {new:.2f} ({new - old:+.2f})")
            print(f"Will update {len(participant_ids)} participant models and then delete game and participants.")
        cur.close()
        conn.close()
        return

    participants_deleted = 0
    games_deleted = 0

    try:
        # Begin transaction
        # Update models first to reflect recomputed state
        for (elo, wins, losses, ties, apples, games, last_played, mid) in updates:
            cur.execute(
                """
                UPDATE models
                SET elo_rating = %s,
                    wins = %s,
                    losses = %s,
                    ties = %s,
                    apples_eaten = %s,
                    games_played = %s,
                    last_played_at = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (elo, wins, losses, ties, apples, games, last_played, mid),
            )

        # Now delete the game and its participants
        cur.execute("DELETE FROM game_participants WHERE game_id = %s", (game_id,))
        participants_deleted = cur.rowcount or 0

        cur.execute("DELETE FROM games WHERE id = %s", (game_id,))
        games_deleted = cur.rowcount or 0

        if participants_deleted < len(participants):
            raise RuntimeError(
                f"Expected to delete {len(participants)} participant rows for {game_id}, "
                f"deleted {participants_deleted}."
            )
        if games_deleted != 1:
            raise RuntimeError(f"Expected to delete 1 game row for {game_id}, deleted {games_deleted}")

        conn.commit()

        # Print a concise summary
        if scope == "global":
            print(
                f"Undid game {game_id}. "
                f"Updated {len(all_models)} models and "
                f"removed {participants_deleted} participants, {games_deleted} game row."
            )
        else:
            print(
                f"Undid game {game_id}. "
                f"Updated {len(participant_ids)} models and "
                f"removed {participants_deleted} participants, {games_deleted} game row."
            )

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

    if delete_replay:
        deleted = _delete_replay_asset(game_id)
        msg = "Replay asset deleted." if deleted else "Replay asset not deleted."
        print(msg)


def main():
    parser = argparse.ArgumentParser(description="Undo a game and recompute ELO/aggregates.")
    parser.add_argument("game_id", help="The game id to undo (UUID)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without applying it")
    parser.add_argument("--scope", choices=["participants", "global"], default="participants",
                        help="Participants: adjust only players of the game; Global: full recompute (default: participants)")
    parser.add_argument("--delete-replay", action="store_true", help="Also delete the replay asset from storage if configured")
    args = parser.parse_args()

    undo_game(
        args.game_id,
        dry_run=args.dry_run,
        scope=args.scope,
        delete_replay=args.delete_replay,
    )


if __name__ == "__main__":
    main()
