#!/usr/bin/env python3
"""
Reset database to clean state.

This script completely wipes all data from the database while preserving
the schema structure. Useful for fresh starts or testing.

Usage:
    python backend/cli/reset_database.py [--confirm]
"""

import os
import sys
import argparse

# Add parent directory to path to import database modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import get_connection, get_database_path


def reset_database(confirm: bool = False) -> bool:
    """
    Reset the database by deleting all data from all tables.

    Args:
        confirm: If True, skip confirmation prompt

    Returns:
        True if reset was successful, False otherwise
    """
    db_path = get_database_path()

    if not confirm:
        print("=" * 70)
        print("⚠️  DATABASE RESET WARNING ⚠️")
        print("=" * 70)
        print(f"Database path: {db_path}")
        print("\nThis will DELETE ALL DATA from the following tables:")
        print("  • models")
        print("  • games")
        print("  • game_participants")
        print("\nThe schema structure will be preserved.")
        print("=" * 70)

        response = input("\nType 'RESET' to confirm: ")

        if response != 'RESET':
            print("❌ Reset cancelled")
            return False

    print("\n🔄 Starting database reset...")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Disable foreign key constraints temporarily
        cursor.execute("PRAGMA foreign_keys = OFF")

        # Delete data from tables in correct order (respect foreign keys)
        tables = ['game_participants', 'games', 'models']

        for table in tables:
            cursor.execute(f"DELETE FROM {table}")
            deleted = cursor.rowcount
            print(f"  ✓ Cleared {table}: {deleted} rows deleted")

        # Re-enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON")

        conn.commit()

        # Vacuum to reclaim space (must be outside transaction)
        cursor.execute("VACUUM")
        print("  ✓ Database vacuumed")

        print("\n" + "=" * 70)
        print("✅ Database reset complete!")
        print("=" * 70)
        print("\nNext steps:")
        print("  1. Run: python backend/cli/sync_openrouter_models.py")
        print("  2. Start Celery workers and dispatch games via dispatch_games.py")
        print("=" * 70 + "\n")

        return True

    except Exception as e:
        print(f"\n❌ Error resetting database: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Reset database to clean state"
    )
    parser.add_argument(
        '--confirm',
        action='store_true',
        help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    success = reset_database(confirm=args.confirm)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
