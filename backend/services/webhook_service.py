"""
Webhook service for sending notifications to external services.

This module handles sending webhook notifications for various events
like model evaluations, game completions, etc.
"""

import os
import requests
import logging
from typing import Dict, Any, Optional
from datetime import datetime


logger = logging.getLogger(__name__)


def send_webhook(url: str, data: Dict[str, Any], timeout: int = 10) -> bool:
    """
    Send a POST request with JSON data to a webhook URL.

    Args:
        url: The webhook URL to send data to
        data: Dictionary of data to send as JSON
        timeout: Request timeout in seconds (default: 10)

    Returns:
        True if webhook was sent successfully, False otherwise
    """
    if not url:
        logger.warning("No webhook URL provided, skipping webhook")
        return False

    try:
        response = requests.post(
            url,
            json=data,
            timeout=timeout,
            headers={'Content-Type': 'application/json'}
        )
        response.raise_for_status()
        logger.info(f"Webhook sent successfully to {url}")
        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send webhook to {url}: {e}")
        return False


def send_evaluation_complete_webhook(
    model_name: str,
    final_elo: float,
    games_played: int,
    wins: int,
    losses: int,
    ties: int,
    total_cost: float,
    webhook_url: Optional[str] = None
) -> bool:
    """
    Send a webhook notification when a model evaluation is complete.

    Args:
        model_name: Name of the evaluated model
        final_elo: Final ELO rating after evaluation
        games_played: Number of games played
        wins: Number of wins
        losses: Number of losses
        ties: Number of ties
        total_cost: Total cost of evaluation
        webhook_url: Override webhook URL (defaults to ZAPIER_WEBHOOK_URL env var)

    Returns:
        True if webhook was sent successfully, False otherwise
    """
    # Use provided URL or fall back to environment variable
    url = webhook_url or os.getenv('ZAPIER_WEBHOOK_URL')

    if not url:
        logger.info("No webhook URL configured, skipping evaluation notification")
        return False

    # Construct the webhook payload
    payload = {
        'event': 'evaluation_complete',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'model': {
            'name': model_name,
            'final_elo': round(final_elo, 2),
            'elo_rating': round(final_elo, 2),  # Alias for compatibility
        },
        'results': {
            'games_played': games_played,
            'wins': wins,
            'losses': losses,
            'ties': ties,
            'win_rate': round((wins / games_played * 100) if games_played > 0 else 0, 1)
        },
        'cost': {
            'total': round(total_cost, 4),
            'per_game': round(total_cost / games_played, 4) if games_played > 0 else 0,
            'currency': 'USD'
        }
    }

    logger.info(f"Sending evaluation complete webhook for model: {model_name}")
    return send_webhook(url, payload)


def send_game_complete_webhook(
    game_id: str,
    model_names: Dict[str, str],
    final_scores: Dict[str, int],
    game_result: Dict[str, str],
    total_cost: float,
    rounds: int,
    webhook_url: Optional[str] = None
) -> bool:
    """
    Send a webhook notification when a game is complete.

    Args:
        game_id: Unique game identifier
        model_names: Dictionary mapping player slot to model name
        final_scores: Dictionary mapping player slot to final score
        game_result: Dictionary mapping player slot to result (won/lost/tied)
        total_cost: Total cost of the game
        rounds: Number of rounds played
        webhook_url: Override webhook URL (defaults to ZAPIER_WEBHOOK_URL env var)

    Returns:
        True if webhook was sent successfully, False otherwise
    """
    # Use provided URL or fall back to environment variable
    url = webhook_url or os.getenv('ZAPIER_WEBHOOK_URL')

    if not url:
        return False

    # Construct the webhook payload
    payload = {
        'event': 'game_complete',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'game': {
            'id': game_id,
            'rounds': rounds
        },
        'players': {
            slot: {
                'name': model_names[slot],
                'score': final_scores[slot],
                'result': game_result[slot]
            }
            for slot in model_names.keys()
        },
        'cost': {
            'total': round(total_cost, 4),
            'currency': 'USD'
        }
    }

    logger.info(f"Sending game complete webhook for game: {game_id}")
    return send_webhook(url, payload)


def send_new_model_webhook(
    model_id: int,
    name: str,
    provider: str,
    model_slug: str,
    pricing_input: Optional[float],
    pricing_output: Optional[float],
    max_completion_tokens: Optional[int],
    webhook_url: Optional[str] = None,
) -> bool:
    """
    Notify when a new model is discovered during catalog sync.

    Args:
        model_id: Database id of the model
        name: Human-readable model name
        provider: Provider extracted from slug
        model_slug: Canonical OpenRouter slug
        pricing_input: Cost per million prompt tokens (if known)
        pricing_output: Cost per million completion tokens (if known)
        max_completion_tokens: Max completion tokens (if known)
        webhook_url: Override webhook URL (defaults to ZAPIER_WEBHOOK_URL env var)
    """
    url = webhook_url or os.getenv("ZAPIER_WEBHOOK_URL")

    if not url:
        logger.info("No webhook URL configured; skipping new-model notification.")
        return False

    payload = {
        "event": "new_model_detected",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "model": {
            "id": model_id,
            "name": name,
            "provider": provider,
            "model_slug": model_slug,
            "pricing_input_per_million": pricing_input,
            "pricing_output_per_million": pricing_output,
            "max_completion_tokens": max_completion_tokens,
            "status": "untested",
            "is_active": False,
        },
    }

    logger.info("Sending new model webhook for %s (%s)", name, model_slug)
    return send_webhook(url, payload)
