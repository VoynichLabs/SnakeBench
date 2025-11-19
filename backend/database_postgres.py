"""
Supabase PostgreSQL database connection and schema management.

This replaces the SQLite database.py with PostgreSQL connections
using Supabase's connection pooler.
"""

import os
import logging
from typing import Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def get_connection_string() -> str:
    """
    Get the Supabase PostgreSQL connection string.

    Returns:
        Connection string for Supabase PostgreSQL
    """
    # Get Supabase URL and parse for connection details
    supabase_url = os.getenv('SUPABASE_URL')
    password = os.getenv('SUPABASE_DB_PASSWORD')

    if not supabase_url or not password:
        raise ValueError("SUPABASE_URL and SUPABASE_DB_PASSWORD are required")

    # Extract project ref from URL (e.g., ohcwbelgdvjxleimagqp)
    # URL format: https://ohcwbelgdvjxleimagqp.supabase.co
    project_ref = supabase_url.split('//')[1].split('.')[0]

    # Connection pooler format
    # postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-us-west-1.pooler.supabase.com:5432/postgres
    # For direct connection (transaction mode), use port 6543
    # For session mode (better for long connections), use port 5432

    conn_string = f"postgresql://postgres.{project_ref}:{password}@aws-0-us-west-1.pooler.supabase.com:6543/postgres"

    return conn_string


def get_connection():
    """
    Get a database connection to Supabase PostgreSQL.

    Returns:
        psycopg2 connection with RealDictCursor (returns rows as dictionaries)
    """
    try:
        conn_string = get_connection_string()
        conn = psycopg2.connect(conn_string, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to Supabase PostgreSQL: {e}")
        raise


def init_database() -> None:
    """
    Initialize the database schema.
    This is now handled by the SQL migration file (001_initial_schema.sql).

    Run that migration in Supabase SQL Editor first!
    """
    print("Database schema should be initialized via Supabase SQL Editor.")
    print("Run backend/migrations/001_initial_schema.sql if you haven't already.")

    # Test the connection
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if tables exist
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('models', 'games', 'game_participants')
            ORDER BY table_name
        """)

        tables = [row['table_name'] for row in cursor.fetchall()]

        if len(tables) == 3:
            print(f"✓ All required tables found: {', '.join(tables)}")
        else:
            print(f"⚠ Only found {len(tables)} tables: {', '.join(tables)}")
            print("Please run backend/migrations/001_initial_schema.sql in Supabase SQL Editor")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"✗ Failed to connect to Supabase PostgreSQL: {e}")
        print("Make sure SUPABASE_URL and SUPABASE_DB_PASSWORD are set in .env")
        raise


if __name__ == "__main__":
    # Test the connection
    print("Testing Supabase PostgreSQL connection...")
    init_database()
