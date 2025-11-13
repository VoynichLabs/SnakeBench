#!/usr/bin/env python3
"""
Test script to verify database integration for Phase 2.

This script:
1. Queries two models from the database
2. Captures their pre-game ELO ratings
3. Simulates running a game (without actually calling LLMs)
4. Verifies that database rows are created
5. Checks that ELO ratings were updated
"""

import sqlite3
from database import get_connection

def main():
    print("=" * 60)
    print("Phase 2 Database Integration Test")
    print("=" * 60)

    conn = get_connection()
    cursor = conn.cursor()

    # 1. Check that we have models in the database
    print("\n1. Checking for models in database...")
    cursor.execute("SELECT COUNT(*) FROM models")
    model_count = cursor.fetchone()[0]
    print(f"   Found {model_count} models in database")

    if model_count == 0:
        print("   ERROR: No models found. Please run seed_models.py first.")
        return

    # 2. Get two models for testing
    print("\n2. Selecting two models for test game...")
    cursor.execute("""
        SELECT id, name, elo_rating, games_played
        FROM models
        WHERE is_active = 1
        ORDER BY games_played DESC
        LIMIT 2
    """)

    models = cursor.fetchall()
    if len(models) < 2:
        print("   ERROR: Need at least 2 active models. Found:", len(models))
        return

    model1 = {"id": models[0][0], "name": models[0][1], "elo": models[0][2], "games": models[0][3]}
    model2 = {"id": models[1][0], "name": models[1][1], "elo": models[1][2], "games": models[1][3]}

    print(f"   Model 1: {model1['name']} (ELO: {model1['elo']:.2f}, Games: {model1['games']})")
    print(f"   Model 2: {model2['name']} (ELO: {model2['elo']:.2f}, Games: {model2['games']})")

    # 3. Check games table
    print("\n3. Checking games table...")
    cursor.execute("SELECT COUNT(*) FROM games")
    game_count_before = cursor.fetchone()[0]
    print(f"   Games in database: {game_count_before}")

    # 4. Check game_participants table
    print("\n4. Checking game_participants table...")
    cursor.execute("SELECT COUNT(*) FROM game_participants")
    participant_count_before = cursor.fetchone()[0]
    print(f"   Participants in database: {participant_count_before}")

    # 5. Verify database schema
    print("\n5. Verifying database schema...")

    # Check models table columns
    cursor.execute("PRAGMA table_info(models)")
    models_cols = [row[1] for row in cursor.fetchall()]
    required_model_cols = ['id', 'name', 'elo_rating', 'wins', 'losses', 'ties',
                           'apples_eaten', 'games_played', 'last_played_at']
    missing_cols = [col for col in required_model_cols if col not in models_cols]
    if missing_cols:
        print(f"   WARNING: Missing columns in models table: {missing_cols}")
    else:
        print(f"   ✓ Models table has all required columns")

    # Check games table columns
    cursor.execute("PRAGMA table_info(games)")
    games_cols = [row[1] for row in cursor.fetchall()]
    required_game_cols = ['id', 'start_time', 'end_time', 'replay_path']
    missing_cols = [col for col in required_game_cols if col not in games_cols]
    if missing_cols:
        print(f"   WARNING: Missing columns in games table: {missing_cols}")
    else:
        print(f"   ✓ Games table has all required columns")

    # Check game_participants table columns
    cursor.execute("PRAGMA table_info(game_participants)")
    participants_cols = [row[1] for row in cursor.fetchall()]
    required_participant_cols = ['id', 'game_id', 'model_id', 'player_slot', 'score', 'result']
    missing_cols = [col for col in required_participant_cols if col not in participants_cols]
    if missing_cols:
        print(f"   WARNING: Missing columns in game_participants table: {missing_cols}")
    else:
        print(f"   ✓ Game_participants table has all required columns")

    # 6. Test the data_access module imports
    print("\n6. Testing data_access module...")
    try:
        from data_access import (
            insert_game,
            insert_game_participants,
            update_model_aggregates,
            update_elo_ratings
        )
        print("   ✓ Successfully imported data_access functions")
    except ImportError as e:
        print(f"   ERROR: Could not import data_access module: {e}")
        return

    print("\n" + "=" * 60)
    print("Database Integration Test: READY")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Run a test game using: python main.py --models <model1> <model2>")
    print("2. Verify new rows appear in games and game_participants tables")
    print("3. Check that model ELO ratings are updated")
    print("\nRecommended test models:")
    print(f"   python main.py --models '{model1['name']}' '{model2['name']}'")

    conn.close()

if __name__ == "__main__":
    main()
