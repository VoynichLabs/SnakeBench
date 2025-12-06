"""
Tests for LLM provider request construction.

Ensures database-only metadata fields aren't forwarded to the OpenAI client.
"""

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import llm_providers  # noqa: E402
from llm_providers import OpenRouterProvider  # noqa: E402


class DummyCompletions:
    """Records kwargs passed to create() and returns a minimal OpenAI-like payload."""

    def __init__(self):
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="UP"))],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        )


def test_openrouter_provider_filters_rating_fields(monkeypatch):
    """
    The provider should not pass database rating fields (e.g., trueskill_mu) to the API.
    """
    completions = DummyCompletions()

    class DummyClient:
        def __init__(self, *args, **kwargs):
            self.chat = SimpleNamespace(completions=completions)
            self.responses = SimpleNamespace(create=lambda **_: None)

    monkeypatch.setattr(llm_providers, "OpenAI", DummyClient)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    provider = OpenRouterProvider(
        api_key="test-key",
        config={
            "name": "test-model",
            "model_name": "openai/test",
            "trueskill_mu": 30.0,
            "trueskill_sigma": 2.5,
            "trueskill_exposed": 25.0,
            "elo_rating": 1500,
            "wins": 10,
            "losses": 5,
        },
    )

    provider.get_response("Say UP")

    assert completions.last_kwargs is not None, "Expected a chat.completions call"
    for forbidden_key in ("trueskill_mu", "trueskill_sigma", "trueskill_exposed"):
        assert forbidden_key not in completions.last_kwargs
