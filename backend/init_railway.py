"""
Master initialization script for Railway deployment.

This script orchestrates the complete database setup process:
1. Create database schema (tables, indexes)
2. Seed models from YAML configuration
3. Import historical games from JSON files
4. Compute ELO ratings from game history

All steps are idempotent and safe to run multiple times.
"""

from database import init_database, get_database_path
from seed_models import seed_models
from import_historical_games import import_games
from recompute_elo import recompute_elo


def initialize_all():
    """Run all initialization steps in sequence."""
    print("=" * 80)
    print("SnakeBench Railway Initialization")
    print("=" * 80)
    print(f"\nDatabase path: {get_database_path()}\n")

    try:
        print("\n[1/4] Initializing database schema...")
        print("-" * 80)
        init_database()

        print("\n[2/4] Seeding models from YAML...")
        print("-" * 80)
        seed_models()

        print("\n[3/4] Importing historical games...")
        print("-" * 80)
        import_games()

        print("\n[4/4] Computing ELO ratings...")
        print("-" * 80)
        recompute_elo()

        print("\n" + "=" * 80)
        print("✓ Initialization complete! SnakeBench is ready to use.")
        print("=" * 80)

    except Exception as e:
        print("\n" + "=" * 80)
        print(f"✗ Initialization failed: {e}")
        print("=" * 80)
        raise


if __name__ == "__main__":
    initialize_all()
