"""
Run the live game support migration on Supabase PostgreSQL.
"""

from database_postgres import get_connection

def run_migration():
    """Apply the live game support migration."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        print("Running migration: add_live_game_support")

        # Add status column to games table
        cursor.execute("""
            ALTER TABLE games
            ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'completed'
        """)
        print("✓ Added status column")

        # Add check constraint for status
        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'games_status_check'
                ) THEN
                    ALTER TABLE games
                    ADD CONSTRAINT games_status_check
                    CHECK(status IN ('queued', 'in_progress', 'completed', 'failed'));
                END IF;
            END $$;
        """)
        print("✓ Added status check constraint")

        # Add current_state column to store live game state JSON
        cursor.execute("""
            ALTER TABLE games
            ADD COLUMN IF NOT EXISTS current_state TEXT
        """)
        print("✓ Added current_state column")

        # Make replay_path nullable (it won't exist for in-progress games)
        cursor.execute("""
            ALTER TABLE games
            ALTER COLUMN replay_path DROP NOT NULL
        """)
        print("✓ Made replay_path nullable")

        # Create index on status for faster live game queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_games_status ON games(status)
        """)
        print("✓ Created index on status")

        # Update existing games to have 'completed' status
        cursor.execute("""
            UPDATE games
            SET status = 'completed'
            WHERE status IS NULL
        """)
        affected = cursor.rowcount
        print(f"✓ Updated {affected} existing games to 'completed' status")

        conn.commit()
        print("\n✅ Migration completed successfully!")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
