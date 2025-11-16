"""
Supabase client initialization for LLMSnake.

This module provides a singleton Supabase client instance configured
with the service role key for backend operations.
"""

import os
import logging
from typing import Optional
from supabase import create_client, Client

logger = logging.getLogger(__name__)


_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Get or create a Supabase client instance.

    Uses environment variables:
    - SUPABASE_URL: The Supabase project URL
    - SUPABASE_SERVICE_ROLE: The service role key (full access)

    Returns:
        Client: Configured Supabase client instance

    Raises:
        ValueError: If required environment variables are missing
    """
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    # Get environment variables
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE')

    if not url:
        raise ValueError("SUPABASE_URL environment variable is required")

    if not key:
        raise ValueError("SUPABASE_SERVICE_ROLE environment variable is required")

    try:
        _supabase_client = create_client(url, key)
        logger.info(f"Supabase client initialized successfully for project: {url}")
        return _supabase_client

    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        raise


def reset_supabase_client():
    """
    Reset the Supabase client singleton.
    Useful for testing or when credentials change.
    """
    global _supabase_client
    _supabase_client = None
    logger.info("Supabase client reset")
