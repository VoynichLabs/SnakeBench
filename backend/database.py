"""
Database configuration and schema management for LLMSnake.

This module provides database connection management with environment-aware
path selection (Railway vs local) and schema initialization.
"""

import os
import sqlite3
from pathlib import Path
from typing import Optional


def get_database_path() -> str:
    """
    Determine the appropriate database path based on environment.

    Returns:
        Path to the SQLite database file.
        - Railway (production): /data/snakebench.db
        - Local (development): backend/snakebench.db
    """
    # Check if running on Railway by looking for RAILWAY_ENVIRONMENT
    if os.getenv('RAILWAY_ENVIRONMENT'):
        # Production: use volume-mounted path
        db_path = '/data/snakebench.db'
        # Ensure the /data directory exists
        os.makedirs('/data', exist_ok=True)
    else:
        # Local development: use backend directory
        backend_dir = Path(__file__).parent
        db_path = str(backend_dir / 'snakebench.db')

    return db_path


def get_connection() -> sqlite3.Connection:
    """
    Get a database connection with appropriate settings.

    Returns:
        sqlite3.Connection: Database connection with row factory enabled.
    """
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn


def init_database() -> None:
    """
    Initialize the database schema with all required tables and indexes.
    Safe to call multiple times (uses IF NOT EXISTS).
    """
    db_path = get_database_path()
    print(f"Initializing database at: {db_path}")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Create models table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                provider TEXT NOT NULL,
                model_slug TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 0,
                test_status TEXT DEFAULT 'untested' CHECK(test_status IN ('untested', 'testing', 'ranked', 'retired')),

                -- ELO and aggregates
                elo_rating REAL DEFAULT 1500.0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                ties INTEGER DEFAULT 0,
                apples_eaten INTEGER DEFAULT 0,
                games_played INTEGER DEFAULT 0,

                -- Pricing and metadata
                pricing_input REAL,
                pricing_output REAL,
                max_completion_tokens INTEGER,
                metadata_json TEXT,

                -- Timestamps
                discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_played_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create games table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id TEXT PRIMARY KEY,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                rounds INTEGER,
                replay_path TEXT NOT NULL,
                board_width INTEGER,
                board_height INTEGER,
                num_apples INTEGER,
                total_score INTEGER,
                total_cost REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create game_participants table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                model_id INTEGER NOT NULL,
                player_slot INTEGER NOT NULL,
                score INTEGER DEFAULT 0,
                result TEXT CHECK(result IN ('won', 'lost', 'tied')),
                death_round INTEGER,
                death_reason TEXT,
                cost REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (game_id) REFERENCES games(id),
                FOREIGN KEY (model_id) REFERENCES models(id),
                UNIQUE(game_id, player_slot)
            )
        """)

        # Create evaluation_queue table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER NOT NULL,
                status TEXT DEFAULT 'queued' CHECK(status IN ('queued', 'running', 'done', 'failed')),
                attempts_remaining INTEGER DEFAULT 10,
                error_message TEXT,
                queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (model_id) REFERENCES models(id),
                UNIQUE(model_id)
            )
        """)

        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_models_elo ON models(elo_rating DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_models_active ON models(is_active, test_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_start_time ON games(start_time DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_end_time ON games(end_time DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_game_participants_model ON game_participants(model_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_game_participants_game ON game_participants(game_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_evaluation_queue_status ON evaluation_queue(status, queued_at)")

        conn.commit()
        print("Database schema initialized successfully")

    except Exception as e:
        conn.rollback()
        print(f"Error initializing database: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    # Allow running this module directly to initialize the database
    init_database()
    print(f"Database ready at: {get_database_path()}")
