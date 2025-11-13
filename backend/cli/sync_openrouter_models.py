#!/usr/bin/env python3
"""
Sync OpenRouter model catalog to the local database.

This script pulls the latest model information from OpenRouter's API and
upserts it into the models table. New models are added with is_active=false
by default and require evaluation before being activated.

Usage:
    python backend/cli/sync_openrouter_models.py [--api-key <key>] [--auto-queue]
"""

import os
import sys
import json
import argparse
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add parent directory to path to import database modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import get_connection
from data_access import enqueue_model


# Cost control parameters (in dollars)
DEFAULT_MAX_COST_PER_GAME = 0.50  # Maximum estimated cost per game
DEFAULT_TOTAL_BUDGET = 10.0  # Maximum total budget for auto-queueing


def fetch_openrouter_models(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch all models from OpenRouter API.

    Args:
        api_key: OpenRouter API key (optional, but recommended)

    Returns:
        List of model dictionaries from OpenRouter

    Raises:
        requests.RequestException: If API call fails
    """
    url = "https://openrouter.ai/api/v1/models"
    headers = {}

    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    print(f"Fetching models from OpenRouter API...")

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()
        models = data.get('data', [])

        print(f"✓ Fetched {len(models)} models from OpenRouter")
        return models

    except requests.RequestException as e:
        print(f"✗ Error fetching models from OpenRouter: {e}")
        raise


def normalize_model_data(openrouter_model: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize OpenRouter model data to our database schema.

    Args:
        openrouter_model: Model data from OpenRouter API

    Returns:
        Dictionary with normalized fields for database insertion
    """
    # Extract pricing (OpenRouter uses per-token pricing)
    pricing = openrouter_model.get('pricing', {})

    # Convert to per-million tokens (OpenRouter may use different units)
    # OpenRouter pricing is typically in dollars per token, multiply by 1M
    prompt_price = pricing.get('prompt')
    completion_price = pricing.get('completion')

    # Handle BigNumberUnion (can be number or string)
    if isinstance(prompt_price, str):
        prompt_price = float(prompt_price)
    if isinstance(completion_price, str):
        completion_price = float(completion_price)

    # Convert to per-million if needed (OpenRouter uses per-token)
    pricing_input_per_m = prompt_price * 1_000_000 if prompt_price else None
    pricing_output_per_m = completion_price * 1_000_000 if completion_price else None

    # Extract other fields
    model_id = openrouter_model.get('id', '')
    name = openrouter_model.get('name', model_id)

    # Derive provider from model ID (format is usually "provider/model-name")
    provider = model_id.split('/')[0] if '/' in model_id else 'unknown'

    # Get context length and max completion tokens
    context_length = openrouter_model.get('context_length')
    top_provider = openrouter_model.get('top_provider', {})
    max_completion_tokens = top_provider.get('max_completion_tokens', context_length)

    # Store additional metadata as JSON
    metadata = {
        'canonical_slug': openrouter_model.get('canonical_slug'),
        'description': openrouter_model.get('description', ''),
        'architecture': openrouter_model.get('architecture', {}),
        'context_length': context_length,
        'supported_parameters': openrouter_model.get('supported_parameters', []),
        'created': openrouter_model.get('created'),
        'hugging_face_id': openrouter_model.get('hugging_face_id'),
    }

    return {
        'name': name,
        'provider': provider,
        'model_slug': model_id,
        'pricing_input_per_m': pricing_input_per_m,
        'pricing_output_per_m': pricing_output_per_m,
        'max_completion_tokens': max_completion_tokens,
        'metadata_json': json.dumps(metadata)
    }


def estimate_game_cost(
    pricing_input_per_m: Optional[float],
    pricing_output_per_m: Optional[float],
    estimated_input_tokens: int = 1000,
    estimated_output_tokens: int = 500
) -> float:
    """
    Estimate the cost of running one game with this model.

    Args:
        pricing_input_per_m: Input pricing per million tokens
        pricing_output_per_m: Output pricing per million tokens
        estimated_input_tokens: Conservative estimate of input tokens per game
        estimated_output_tokens: Conservative estimate of output tokens per game

    Returns:
        Estimated cost in dollars, or float('inf') if pricing unavailable
    """
    if pricing_input_per_m is None or pricing_output_per_m is None:
        return float('inf')  # Can't estimate without pricing

    input_cost = (estimated_input_tokens / 1_000_000) * pricing_input_per_m
    output_cost = (estimated_output_tokens / 1_000_000) * pricing_output_per_m

    return input_cost + output_cost


def upsert_model(model_data: Dict[str, Any]) -> Optional[int]:
    """
    Insert or update a model in the database.

    Args:
        model_data: Normalized model data

    Returns:
        Model ID if successful, None otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Check if model already exists
        cursor.execute("""
            SELECT id, is_active, test_status, games_played
            FROM models
            WHERE model_slug = ?
        """, (model_data['model_slug'],))

        existing = cursor.fetchone()

        if existing:
            model_id = existing[0]
            is_active = existing[1]
            test_status = existing[2]
            games_played = existing[3]

            # Update pricing and metadata only, preserve status and stats
            cursor.execute("""
                UPDATE models
                SET name = ?,
                    provider = ?,
                    pricing_input_per_m = ?,
                    pricing_output_per_m = ?,
                    max_completion_tokens = ?,
                    metadata_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                model_data['name'],
                model_data['provider'],
                model_data['pricing_input_per_m'],
                model_data['pricing_output_per_m'],
                model_data['max_completion_tokens'],
                model_data['metadata_json'],
                model_id
            ))

            print(f"  ↻ Updated: {model_data['name']} (already has {games_played} games)")
        else:
            # Insert new model (inactive by default)
            cursor.execute("""
                INSERT INTO models (
                    name, provider, model_slug,
                    pricing_input_per_m, pricing_output_per_m,
                    max_completion_tokens, metadata_json,
                    is_active, test_status,
                    discovered_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'untested', ?)
            """, (
                model_data['name'],
                model_data['provider'],
                model_data['model_slug'],
                model_data['pricing_input_per_m'],
                model_data['pricing_output_per_m'],
                model_data['max_completion_tokens'],
                model_data['metadata_json'],
                datetime.now().isoformat()
            ))

            model_id = cursor.lastrowid
            print(f"  + Added: {model_data['name']} (new, untested)")

        conn.commit()
        return model_id

    except Exception as e:
        print(f"  ✗ Error upserting model {model_data.get('name')}: {e}")
        conn.rollback()
        return None

    finally:
        conn.close()


def sync_models(
    api_key: Optional[str] = None,
    auto_queue: bool = False,
    max_cost_per_game: float = DEFAULT_MAX_COST_PER_GAME,
    total_budget: float = DEFAULT_TOTAL_BUDGET
) -> Dict[str, int]:
    """
    Main sync function to pull OpenRouter catalog and upsert models.

    Args:
        api_key: OpenRouter API key
        auto_queue: If True, automatically queue untested models within budget
        max_cost_per_game: Maximum cost per game for auto-queueing
        total_budget: Total budget for auto-queueing new models

    Returns:
        Dictionary with sync statistics
    """
    print("=" * 70)
    print("OpenRouter Model Sync")
    print("=" * 70)

    # Fetch models from OpenRouter
    try:
        openrouter_models = fetch_openrouter_models(api_key)
    except Exception as e:
        print(f"Failed to fetch models: {e}")
        return {'error': 1}

    # Process each model
    stats = {
        'total': len(openrouter_models),
        'added': 0,
        'updated': 0,
        'skipped': 0,
        'queued': 0
    }

    models_to_queue = []

    print(f"\nProcessing {stats['total']} models...")

    for or_model in openrouter_models:
        try:
            # Normalize and upsert
            normalized = normalize_model_data(or_model)
            model_id = upsert_model(normalized)

            if model_id is None:
                stats['skipped'] += 1
                continue

            # Check if this is a new model
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT test_status, pricing_input_per_m, pricing_output_per_m
                FROM models
                WHERE id = ?
            """, (model_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                test_status = row[0]

                if test_status == 'untested':
                    stats['added'] += 1

                    if auto_queue:
                        # Estimate cost and add to queue candidates
                        cost = estimate_game_cost(row[1], row[2])

                        if cost <= max_cost_per_game:
                            models_to_queue.append({
                                'id': model_id,
                                'name': normalized['name'],
                                'cost': cost
                            })
                else:
                    stats['updated'] += 1

        except Exception as e:
            print(f"  ✗ Error processing model: {e}")
            stats['skipped'] += 1

    # Auto-queue untested models within budget
    if auto_queue and models_to_queue:
        print(f"\n{'=' * 70}")
        print(f"Auto-queueing untested models (budget: ${total_budget:.2f})")
        print(f"{'=' * 70}")

        # Sort by cost (cheapest first)
        models_to_queue.sort(key=lambda x: x['cost'])

        running_cost = 0.0

        for model_info in models_to_queue:
            estimated_total_cost = model_info['cost'] * 10  # 10 games

            if running_cost + estimated_total_cost > total_budget:
                print(f"  ⊘ Budget limit reached, {len(models_to_queue) - stats['queued']} models not queued")
                break

            if enqueue_model(model_info['id']):
                stats['queued'] += 1
                running_cost += estimated_total_cost
                print(f"  ✓ Queued: {model_info['name']} (est. ${estimated_total_cost:.3f} for 10 games)")

    # Print summary
    print(f"\n{'=' * 70}")
    print("Sync Complete")
    print(f"{'=' * 70}")
    print(f"Total models processed: {stats['total']}")
    print(f"New models added: {stats['added']}")
    print(f"Existing models updated: {stats['updated']}")
    print(f"Models skipped: {stats['skipped']}")

    if auto_queue:
        print(f"Models queued for evaluation: {stats['queued']}")

    print(f"{'=' * 70}\n")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Sync OpenRouter model catalog to local database"
    )
    parser.add_argument(
        '--api-key',
        type=str,
        help="OpenRouter API key (or set OPENROUTER_API_KEY env var)"
    )
    parser.add_argument(
        '--auto-queue',
        action='store_true',
        help="Automatically queue untested models for evaluation within budget"
    )
    parser.add_argument(
        '--max-cost-per-game',
        type=float,
        default=DEFAULT_MAX_COST_PER_GAME,
        help=f"Maximum cost per game for auto-queueing (default: ${DEFAULT_MAX_COST_PER_GAME})"
    )
    parser.add_argument(
        '--budget',
        type=float,
        default=DEFAULT_TOTAL_BUDGET,
        help=f"Total budget for auto-queueing new models (default: ${DEFAULT_TOTAL_BUDGET})"
    )

    args = parser.parse_args()

    # Get API key from args or environment
    api_key = args.api_key or os.getenv('OPENROUTER_API_KEY')

    if not api_key:
        print("Warning: No API key provided. Some features may be limited.")
        print("Set OPENROUTER_API_KEY environment variable or use --api-key flag.")

    # Run sync
    sync_models(
        api_key=api_key,
        auto_queue=args.auto_queue,
        max_cost_per_game=args.max_cost_per_game,
        total_budget=args.budget
    )


if __name__ == "__main__":
    main()
