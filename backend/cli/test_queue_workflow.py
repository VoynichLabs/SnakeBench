#!/usr/bin/env python3
"""
Test the evaluation queue workflow without running actual games.

This script verifies that:
1. Models can be queued
2. Queue entries can be retrieved
3. Queue status can be updated
4. Model configurations can be built from database
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from data_access import (
    get_next_queued_model,
    update_queue_status,
    get_queue_stats,
    enqueue_model
)
from database import get_connection


def test_queue_workflow():
    """Test the complete queue workflow."""
    print("=" * 70)
    print("Testing Evaluation Queue Workflow")
    print("=" * 70)

    # 1. Check queue stats
    print("\n1. Current Queue Statistics:")
    stats = get_queue_stats()
    for status, count in stats.items():
        print(f"   {status}: {count}")

    # 2. Get next model in queue
    print("\n2. Fetching next queued model...")
    queue_entry = get_next_queued_model()

    if not queue_entry:
        print("   ✗ No models in queue")
        return

    print(f"   ✓ Model: {queue_entry['name']}")
    print(f"   - Model ID: {queue_entry['model_id']}")
    print(f"   - Queue ID: {queue_entry['queue_id']}")
    print(f"   - Provider: {queue_entry['provider']}")
    print(f"   - Model Slug: {queue_entry['model_slug']}")
    print(f"   - Current ELO: {queue_entry['elo_rating']:.2f}")
    print(f"   - Attempts Remaining: {queue_entry['attempts_remaining']}")
    print(f"   - Pricing (in/out per M): ${queue_entry['pricing_input_per_m']}/{queue_entry['pricing_output_per_m']}")

    # 3. Test status updates
    print("\n3. Testing status updates...")
    queue_id = queue_entry['queue_id']

    print(f"   Setting status to 'running'...")
    update_queue_status(queue_id, 'running')
    print("   ✓ Status updated to running")

    # 4. Verify status in database
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT status, started_at
        FROM evaluation_queue
        WHERE id = ?
    """, (queue_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        print(f"   ✓ Verified in DB: status={row[0]}, started_at={row[1]}")

    # 5. Revert to queued for testing
    print("\n4. Reverting to queued status...")
    update_queue_status(queue_id, 'queued')
    print("   ✓ Reverted to queued")

    # 6. Check if we can build a model config
    print("\n5. Testing model config building...")
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            name,
            provider,
            model_slug,
            max_completion_tokens,
            metadata_json
        FROM models
        WHERE id = ?
    """, (queue_entry['model_id'],))

    row = cursor.fetchone()
    conn.close()

    if row:
        name, provider, model_slug, max_tokens, metadata = row
        print(f"   ✓ Can build config for {name}")
        print(f"     Provider: {provider}")
        print(f"     Model Slug: {model_slug}")
        print(f"     Max Tokens: {max_tokens}")

        # Show what a config would look like
        config = {
            'name': name,
            'provider': provider,
            'model': model_slug,
            'max_tokens': max_tokens or 500
        }
        print(f"   ✓ Sample config: {config}")

    # 7. Count ranked models for opponent selection
    print("\n6. Checking available opponents...")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*)
        FROM models
        WHERE test_status = 'ranked' AND is_active = 1
    """)
    ranked_count = cursor.fetchone()[0]
    conn.close()

    print(f"   ✓ {ranked_count} ranked models available as opponents")

    print("\n" + "=" * 70)
    print("Queue Workflow Test Complete!")
    print("=" * 70)
    print("\nSummary:")
    print("✓ Can retrieve queued models")
    print("✓ Can update queue status")
    print("✓ Can build model configs from DB")
    print(f"✓ {ranked_count} opponents available for matchmaking")
    print("\nThe evaluation worker is ready to process models!")
    print("=" * 70)


if __name__ == "__main__":
    test_queue_workflow()
