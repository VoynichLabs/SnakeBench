"""
Seed the models table from the YAML model list.

This script loads models from backend/model_lists/model_list.yaml and
inserts them into the database, preserving pricing, provider, and metadata.
"""

import json
import sqlite3
from pathlib import Path
import yaml

from database_postgres import get_connection, get_database_path


def load_yaml_models():
    """Load models from the YAML configuration file."""
    yaml_path = Path(__file__).parent / 'model_lists' / 'model_list.yaml'

    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)

    return data.get('models', [])


def seed_models():
    """
    Seed the models table from YAML.

    Sets is_active=True for all seeded models initially, since these are
    the manually curated models that are ready to play.
    """
    print(f"Loading models from YAML...")
    models = load_yaml_models()
    print(f"Found {len(models)} models in YAML")

    conn = get_connection()
    cursor = conn.cursor()

    inserted = 0
    updated = 0

    try:
        for model in models:
            # Extract fields from YAML
            name = model.get('name')
            model_name = model.get('model_name')
            provider = model.get('provider')
            max_completion_tokens = model.get('max_completion_tokens')

            # Extract pricing if available
            pricing = model.get('pricing', {})
            pricing_input = pricing.get('input')
            pricing_output = pricing.get('output')

            # Store additional metadata as JSON
            metadata = {}
            if 'api_type' in model:
                metadata['api_type'] = model['api_type']
            if 'reasoning_effort' in model:
                metadata['reasoning_effort'] = model['reasoning_effort']
            if 'max_tokens' in model:
                metadata['max_tokens'] = model['max_tokens']
            if 'pricing' in model:
                metadata['pricing_date'] = pricing.get('date')

            metadata_json = json.dumps(metadata) if metadata else None

            # Check if model already exists
            cursor.execute("SELECT id FROM models WHERE name = %s", (name,))
            existing = cursor.fetchone()

            if existing:
                # Update existing model
                cursor.execute("""
                    UPDATE models
                    SET provider = %s,
                        model_slug = %s,
                        pricing_input = %s,
                        pricing_output = %s,
                        max_completion_tokens = %s,
                        metadata_json = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE name = %s
                """, (
                    provider,
                    model_name,
                    pricing_input,
                    pricing_output,
                    max_completion_tokens,
                    metadata_json,
                    name
                ))
                updated += 1
                print(f"  Updated: {name}")
            else:
                # Insert new model (set is_active=True for YAML models)
                cursor.execute("""
                    INSERT INTO models (
                        name, provider, model_slug,
                        is_active, test_status,
                        pricing_input, pricing_output,
                        max_completion_tokens, metadata_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    name,
                    provider,
                    model_name,
                    True,  # YAML models are active by default
                    'ranked',  # YAML models are considered pre-ranked
                    pricing_input,
                    pricing_output,
                    max_completion_tokens,
                    metadata_json
                ))
                inserted += 1
                print(f"  Inserted: {name}")

        conn.commit()
        print(f"\nSeeding complete:")
        print(f"  - Inserted: {inserted} new models")
        print(f"  - Updated: {updated} existing models")

    except Exception as e:
        conn.rollback()
        print(f"Error seeding models: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    print(f"Database path: {get_database_path()}\n")
    seed_models()
