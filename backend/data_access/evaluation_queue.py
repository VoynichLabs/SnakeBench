"""
Evaluation queue management functions.

Provides functions for queueing models for evaluation, updating queue status,
and retrieving queued models for processing.
"""

import sqlite3
from typing import Optional, Dict, Any, List
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_postgres import get_connection


def enqueue_model(model_id: int, attempts: int = 10) -> bool:
    """
    Add a model to the evaluation queue.

    Args:
        model_id: ID of the model to queue
        attempts: Number of evaluation games to run (default: 10)

    Returns:
        True if queued successfully, False if already queued
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO evaluation_queue (model_id, attempts_remaining)
            VALUES (%s, %s)
        """, (model_id, attempts))

        conn.commit()
        print(f"Model {model_id} queued for evaluation with {attempts} games")
        return True

    except Exception as integrity_error:
        # Model already in queue (psycopg2.IntegrityError or UniqueViolation)
        if 'unique' in str(integrity_error).lower() or 'duplicate' in str(integrity_error).lower():
            print(f"Model {model_id} is already in the evaluation queue")
            return False
        # Re-raise if it's a different error
        raise

    except Exception as e:
        print(f"Error queueing model {model_id}: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()


def get_next_queued_model() -> Optional[Dict[str, Any]]:
    """
    Get the next model waiting in the queue.

    Returns:
        Dictionary with model info and queue entry, or None if queue is empty
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                eq.id as queue_id,
                eq.model_id,
                eq.attempts_remaining,
                m.name,
                m.provider,
                m.model_slug,
                m.elo_rating,
                m.pricing_input,
                m.pricing_output,
                m.max_completion_tokens,
                m.metadata_json
            FROM evaluation_queue eq
            JOIN models m ON eq.model_id = m.id
            WHERE eq.status = 'queued'
                AND m.pricing_input > 0
            ORDER BY
                (COALESCE(m.pricing_input, 0) + COALESCE(m.pricing_output, 0)) ASC,
                eq.queued_at ASC
            LIMIT 1
        """)

        row = cursor.fetchone()

        if row is None:
            return None

        return {
            'queue_id': row['queue_id'],
            'model_id': row['model_id'],
            'attempts_remaining': row['attempts_remaining'],
            'name': row['name'],
            'provider': row['provider'],
            'model_slug': row['model_slug'],
            'elo_rating': row['elo_rating'],
            'pricing_input': row['pricing_input'],
            'pricing_output': row['pricing_output'],
            'max_completion_tokens': row['max_completion_tokens'],
            'metadata_json': row['metadata_json']
        }

    finally:
        conn.close()


def update_queue_status(
    queue_id: int,
    status: str,
    error_message: Optional[str] = None
) -> None:
    """
    Update the status of a queue entry.

    Args:
        queue_id: ID of the queue entry
        status: New status ('queued', 'running', 'done', 'failed')
        error_message: Optional error message if status is 'failed'
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        timestamp_field = None
        if status == 'running':
            timestamp_field = 'started_at'
        elif status in ('done', 'failed'):
            timestamp_field = 'completed_at'

        if timestamp_field:
            cursor.execute(f"""
                UPDATE evaluation_queue
                SET status = %s,
                    error_message = %s,
                    {timestamp_field} = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (status, error_message, datetime.now().isoformat(), queue_id))
        else:
            cursor.execute("""
                UPDATE evaluation_queue
                SET status = %s,
                    error_message = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (status, error_message, queue_id))

        conn.commit()

    except Exception as e:
        print(f"Error updating queue status: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()


def decrement_attempts(queue_id: int) -> int:
    """
    Decrement the attempts_remaining counter for a queue entry.

    Args:
        queue_id: ID of the queue entry

    Returns:
        New attempts_remaining value
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE evaluation_queue
            SET attempts_remaining = attempts_remaining - 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (queue_id,))

        cursor.execute("""
            SELECT attempts_remaining
            FROM evaluation_queue
            WHERE id = %s
        """, (queue_id,))

        result = cursor.fetchone()
        conn.commit()

        return result['attempts_remaining'] if result else 0

    except Exception as e:
        print(f"Error decrementing attempts: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()


def get_queue_stats() -> Dict[str, int]:
    """
    Get statistics about the evaluation queue.

    Returns:
        Dictionary with counts by status
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM evaluation_queue
            GROUP BY status
        """)

        stats = {
            'queued': 0,
            'running': 0,
            'done': 0,
            'failed': 0
        }

        for row in cursor.fetchall():
            stats[row['status']] = row['count']

        return stats

    finally:
        conn.close()


def remove_from_queue(model_id: int) -> bool:
    """
    Remove a model from the evaluation queue.

    Args:
        model_id: ID of the model to remove

    Returns:
        True if removed, False if not in queue
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            DELETE FROM evaluation_queue
            WHERE model_id = %s
        """, (model_id,))

        deleted = cursor.rowcount > 0
        conn.commit()

        return deleted

    except Exception as e:
        print(f"Error removing model from queue: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()
