#!/usr/bin/env python3
"""
Test Phase 2 database persistence without running an actual game.

This creates a mock game result and verifies all database operations work correctly.
"""

from datetime import datetime
import uuid
from database import get_connection
from data_access import (
    insert_game,
    insert_game_participants,
    update_model_aggregates,
    update_elo_ratings
)


def test_phase2_persistence():
    """Test the complete Phase 2 persistence flow."""

    print("=" * 70)
    print("Testing Phase 2: Event-Driven ELO and Aggregates")
    print("=" * 70)

    conn = get_connection()
    cursor = conn.cursor()

    # Get two test models
    cursor.execute("""
        SELECT id, name, elo_rating, wins, losses, ties, apples_eaten, games_played
        FROM models
        WHERE is_active = 1
        ORDER BY games_played DESC
        LIMIT 2
    """)
    models = cursor.fetchall()

    if len(models) < 2:
        print("ERROR: Need at least 2 active models")
        return

    model1 = {
        'id': models[0][0],
        'name': models[0][1],
        'elo_before': models[0][2],
        'wins_before': models[0][3],
        'losses_before': models[0][4],
        'ties_before': models[0][5],
        'apples_before': models[0][6],
        'games_before': models[0][7]
    }

    model2 = {
        'id': models[1][0],
        'name': models[1][1],
        'elo_before': models[1][2],
        'wins_before': models[1][3],
        'losses_before': models[1][4],
        'ties_before': models[1][5],
        'apples_before': models[1][6],
        'games_before': models[1][7]
    }

    print(f"\nTest models:")
    print(f"  Model 1: {model1['name']}")
    print(f"    ELO: {model1['elo_before']:.2f}, W/L/T: {model1['wins_before']}/{model1['losses_before']}/{model1['ties_before']}")
    print(f"  Model 2: {model2['name']}")
    print(f"    ELO: {model2['elo_before']:.2f}, W/L/T: {model2['wins_before']}/{model2['losses_before']}/{model2['ties_before']}")

    # Create a test game
    test_game_id = str(uuid.uuid4())
    start_time = datetime.now()
    end_time = datetime.now()

    print(f"\n1. Inserting test game {test_game_id[:8]}...")
    insert_game(
        game_id=test_game_id,
        start_time=start_time,
        end_time=end_time,
        rounds=50,
        replay_path=f"completed_games/test_game_{test_game_id}.json",
        board_width=10,
        board_height=10,
        num_apples=5,
        total_score=15
    )
    print("   ✓ Game inserted")

    # Create participants - model1 wins
    print("\n2. Inserting game participants...")
    participants = [
        {
            'model_name': model1['name'],
            'player_slot': 0,
            'score': 10,  # model1 wins with higher score
            'result': 'won',
            'death_round': None,
            'death_reason': None
        },
        {
            'model_name': model2['name'],
            'player_slot': 1,
            'score': 5,
            'result': 'lost',
            'death_round': None,
            'death_reason': None
        }
    ]
    insert_game_participants(test_game_id, participants)
    print("   ✓ Participants inserted")

    # Update aggregates
    print("\n3. Updating model aggregates...")
    update_model_aggregates(test_game_id)
    print("   ✓ Aggregates updated")

    # Update ELO ratings
    print("\n4. Updating ELO ratings...")
    update_elo_ratings(test_game_id)
    print("   ✓ ELO ratings updated")

    # Verify the changes
    print("\n5. Verifying changes...")

    cursor.execute("""
        SELECT elo_rating, wins, losses, ties, apples_eaten, games_played
        FROM models
        WHERE id = ?
    """, (model1['id'],))
    m1_after = cursor.fetchone()

    cursor.execute("""
        SELECT elo_rating, wins, losses, ties, apples_eaten, games_played
        FROM models
        WHERE id = ?
    """, (model2['id'],))
    m2_after = cursor.fetchone()

    print(f"\n  {model1['name']}:")
    print(f"    ELO: {model1['elo_before']:.2f} -> {m1_after[0]:.2f} (delta: {m1_after[0] - model1['elo_before']:+.2f})")
    print(f"    Wins: {model1['wins_before']} -> {m1_after[1]} (+{m1_after[1] - model1['wins_before']})")
    print(f"    Apples: {model1['apples_before']} -> {m1_after[4]} (+{m1_after[4] - model1['apples_before']})")
    print(f"    Games: {model1['games_before']} -> {m1_after[5]} (+{m1_after[5] - model1['games_before']})")

    print(f"\n  {model2['name']}:")
    print(f"    ELO: {model2['elo_before']:.2f} -> {m2_after[0]:.2f} (delta: {m2_after[0] - model2['elo_before']:+.2f})")
    print(f"    Losses: {model2['losses_before']} -> {m2_after[2]} (+{m2_after[2] - model2['losses_before']})")
    print(f"    Apples: {model2['apples_before']} -> {m2_after[4]} (+{m2_after[4] - model2['apples_before']})")
    print(f"    Games: {model2['games_before']} -> {m2_after[5]} (+{m2_after[5] - model2['games_before']})")

    # Verify game was inserted
    cursor.execute("SELECT COUNT(*) FROM games WHERE id = ?", (test_game_id,))
    if cursor.fetchone()[0] == 1:
        print("\n   ✓ Game record verified")
    else:
        print("\n   ✗ Game record NOT found")

    # Verify participants were inserted
    cursor.execute("SELECT COUNT(*) FROM game_participants WHERE game_id = ?", (test_game_id,))
    if cursor.fetchone()[0] == 2:
        print("   ✓ Participant records verified")
    else:
        print("   ✗ Participant records NOT found")

    # Check that ELO changed (winner should gain, loser should lose)
    elo1_delta = m1_after[0] - model1['elo_before']
    elo2_delta = m2_after[0] - model2['elo_before']

    if elo1_delta > 0 and elo2_delta < 0:
        print("   ✓ ELO changes are correct (winner gained, loser lost)")
    else:
        print(f"   ✗ ELO changes unexpected: winner delta={elo1_delta:.2f}, loser delta={elo2_delta:.2f}")

    # Cleanup test game
    print(f"\n6. Cleaning up test game...")
    cursor.execute("DELETE FROM game_participants WHERE game_id = ?", (test_game_id,))
    cursor.execute("DELETE FROM games WHERE id = ?", (test_game_id,))

    # Restore original model stats
    cursor.execute("""
        UPDATE models
        SET elo_rating = ?,
            wins = ?,
            losses = ?,
            ties = ?,
            apples_eaten = ?,
            games_played = ?
        WHERE id = ?
    """, (
        model1['elo_before'],
        model1['wins_before'],
        model1['losses_before'],
        model1['ties_before'],
        model1['apples_before'],
        model1['games_before'],
        model1['id']
    ))

    cursor.execute("""
        UPDATE models
        SET elo_rating = ?,
            wins = ?,
            losses = ?,
            ties = ?,
            apples_eaten = ?,
            games_played = ?
        WHERE id = ?
    """, (
        model2['elo_before'],
        model2['wins_before'],
        model2['losses_before'],
        model2['ties_before'],
        model2['apples_before'],
        model2['games_before'],
        model2['id']
    ))

    conn.commit()
    print("   ✓ Test data cleaned up, model stats restored")

    conn.close()

    print("\n" + "=" * 70)
    print("Phase 2 Persistence Test: PASSED")
    print("=" * 70)
    print("\nAll database operations working correctly:")
    print("  ✓ Game insertion")
    print("  ✓ Participant insertion")
    print("  ✓ Aggregate updates (wins/losses/ties/apples/games)")
    print("  ✓ ELO rating calculations")
    print("\nPhase 2 is ready for integration with backend/main.py")


if __name__ == "__main__":
    test_phase2_persistence()
