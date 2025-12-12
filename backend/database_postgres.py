"""
PostgreSQL database connection and schema management.

Connects to PostgreSQL using DATABASE_URL (preferred) or individual
PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE environment variables.

This module is provider-agnostic and works with Railway, Render, Heroku,
or any PostgreSQL instance.
"""

import os
import logging
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def get_connection_string() -> str:
    """
    Get the PostgreSQL connection string.

    Priority:
    1. DATABASE_URL environment variable (standard for Railway, Heroku, etc.)
    2. Individual PG* environment variables (PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE)

    Returns:
        Connection string for PostgreSQL

    Raises:
        ValueError: If no valid connection configuration is found
    """
    # Prefer DATABASE_URL (standard for Railway, Heroku, Render, etc.)
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        return database_url

    # Fallback to individual PG* variables
    pghost = os.getenv('PGHOST')
    pgport = os.getenv('PGPORT', '5432')
    pguser = os.getenv('PGUSER')
    pgpassword = os.getenv('PGPASSWORD')
    pgdatabase = os.getenv('PGDATABASE')

    if pghost and pguser and pgpassword and pgdatabase:
        return f"postgresql://{pguser}:{pgpassword}@{pghost}:{pgport}/{pgdatabase}"

    raise ValueError(
        "Database connection not configured. "
        "Set DATABASE_URL or PGHOST/PGUSER/PGPASSWORD/PGDATABASE environment variables."
    )


def get_connection():
    """
    Get a database connection to PostgreSQL.

    Returns:
        psycopg2 connection with RealDictCursor (returns rows as dictionaries)
    """
    try:
        conn_string = get_connection_string()
        # Railway and most cloud providers require SSL
        conn = psycopg2.connect(conn_string, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        raise


def init_database() -> None:
    """
    Initialize the database schema.
    This is now handled by the SQL migration file (001_initial_schema.sql).

    Run that migration in your database admin tool or via Drizzle.
    """
    print("Database schema should be initialized via migrations.")
    print("For ARC Explainer, run: npm run db:push")

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
            print(f"[OK] All required tables found: {', '.join(tables)}")
        else:
            print(f"[WARN] Only found {len(tables)} tables: {', '.join(tables)}")
            print("Run migrations to create missing tables.")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"[ERROR] Failed to connect to PostgreSQL: {e}")
        print("Make sure DATABASE_URL is set correctly.")
        raise


if __name__ == "__main__":
    # Test the connection
    print("Testing PostgreSQL connection...")
    init_database()
