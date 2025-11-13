"""
Import historical games from completed_games/*.json into the database.

This script scans all game replay files and imports them into the
games and game_participants tables, preserving the link to the replay file.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from database import get_connection, get_database_path


def parse_game_json(game_path: Path) -> Dict[str, Any]:
    """Parse a game JSON file and extract relevant information."""
    with open(game_path, 'r') as f:
        data = json.load(f)

    metadata = data.get('metadata', {})
    rounds = data.get('rounds', [])

    # Extract basic game info
    game_info = {
        'game_id': metadata.get('game_id'),
        'start_time': metadata.get('start_time'),
        'end_time': metadata.get('end_time'),
        'rounds': metadata.get('actual_rounds', len(rounds)),
        'replay_path': str(game_path),
    }

    # Extract board dimensions and apples from first round
    if rounds:
        first_round = rounds[0]
        game_info['board_width'] = first_round.get('width', 10)
        game_info['board_height'] = first_round.get('height', 10)
        game_info['num_apples'] = len(first_round.get('apples', []))

    # Extract participant info
    models = metadata.get('models', {})
    results = metadata.get('game_result', {})
    scores = metadata.get('final_scores', {})
    death_info = metadata.get('death_info', {})

    participants = []
    total_score = 0

    for player_slot, model_name in models.items():
        score = scores.get(player_slot, 0)
        total_score += score

        death = death_info.get(player_slot, {})

        participant = {
            'player_slot': int(player_slot) - 1,  # Convert 1-indexed to 0-indexed
            'model_name': model_name,
            'score': score,
            'result': results.get(player_slot, 'tied'),
            'death_round': death.get('round') if death else None,
            'death_reason': death.get('reason') if death else None,
        }
        participants.append(participant)

    game_info['total_score'] = total_score
    game_info['participants'] = participants

    return game_info


def get_model_id_by_name(cursor: sqlite3.Cursor, model_name: str) -> int:
    """
    Look up model ID by name.

    The historical game JSON files have model names without provider prefixes
    (due to clean_model_name function in main.py), but our database has them
    with prefixes. Try multiple matching strategies.
    """
    # Try exact match first
    cursor.execute("SELECT id FROM models WHERE name = ?", (model_name,))
    result = cursor.fetchone()
    if result:
        return result[0]

    # Try matching on the part after the last '/' in model_slug or name
    cursor.execute("""
        SELECT id FROM models
        WHERE name LIKE '%/' || ?
        OR model_slug LIKE '%/' || ?
    """, (model_name, model_name))
    result = cursor.fetchone()
    if result:
        return result[0]

    # Try case-insensitive partial match on name or model_slug
    cursor.execute("""
        SELECT id FROM models
        WHERE LOWER(name) LIKE '%' || LOWER(?) || '%'
        OR LOWER(model_slug) LIKE '%' || LOWER(?) || '%'
        LIMIT 1
    """, (model_name, model_name))
    result = cursor.fetchone()
    if result:
        return result[0]

    # If model not found, log it but don't fail
    print(f"  WARNING: Model '{model_name}' not found in database")
    return None


def import_games():
    """
    Import all historical games from completed_games/*.json.
    """
    games_dir = Path(__file__).parent / 'completed_games'

    if not games_dir.exists():
        print(f"Error: Games directory not found: {games_dir}")
        return

    # Get all game JSON files (exclude game_index.json)
    game_files = sorted([
        f for f in games_dir.glob('snake_game_*.json')
    ])

    print(f"Found {len(game_files)} game files to import\n")

    conn = get_connection()
    cursor = conn.cursor()

    imported = 0
    skipped = 0
    errors = 0

    try:
        for game_file in game_files:
            try:
                # Parse the game JSON
                game_info = parse_game_json(game_file)

                # Check if game already exists
                cursor.execute("SELECT id FROM games WHERE id = ?", (game_info['game_id'],))
                if cursor.fetchone():
                    skipped += 1
                    if skipped <= 5:
                        print(f"  Skipped (exists): {game_info['game_id']}")
                    continue

                # Insert game record
                cursor.execute("""
                    INSERT INTO games (
                        id, start_time, end_time, rounds, replay_path,
                        board_width, board_height, num_apples, total_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    game_info['game_id'],
                    game_info['start_time'],
                    game_info['end_time'],
                    game_info['rounds'],
                    game_info['replay_path'],
                    game_info['board_width'],
                    game_info['board_height'],
                    game_info['num_apples'],
                    game_info['total_score'],
                ))

                # Insert participant records
                for participant in game_info['participants']:
                    model_id = get_model_id_by_name(cursor, participant['model_name'])

                    if model_id is None:
                        # Skip this participant if model not found
                        continue

                    cursor.execute("""
                        INSERT INTO game_participants (
                            game_id, model_id, player_slot, score,
                            result, death_round, death_reason
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        game_info['game_id'],
                        model_id,
                        participant['player_slot'],
                        participant['score'],
                        participant['result'],
                        participant['death_round'],
                        participant['death_reason'],
                    ))

                imported += 1
                if imported <= 10 or imported % 100 == 0:
                    print(f"  Imported: {game_info['game_id']} ({imported}/{len(game_files)})")

            except Exception as e:
                errors += 1
                print(f"  ERROR processing {game_file.name}: {e}")
                if errors > 10:
                    print("  Too many errors, stopping import")
                    break

        conn.commit()
        print(f"\nImport complete:")
        print(f"  - Imported: {imported} games")
        print(f"  - Skipped: {skipped} (already existed)")
        print(f"  - Errors: {errors}")

    except Exception as e:
        conn.rollback()
        print(f"Fatal error during import: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    print(f"Database path: {get_database_path()}\n")
    import_games()
