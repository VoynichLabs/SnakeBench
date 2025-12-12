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
from llm_providers import OpenRouterProvider, OpenAIProvider  # noqa: E402


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


class DummyResponses:
    """Records kwargs passed to responses.create() and returns a minimal Responses-like payload."""

    def __init__(self):
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(
            output=[
                SimpleNamespace(
                    content=[
                        SimpleNamespace(type="output_text", text="UP"),
                    ]
                )
            ],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )


def test_openai_provider_uses_responses_input_items(monkeypatch):
    """
    Direct OpenAI provider should call Responses API with input role/content items
    (not chat messages), and should strip "openai/" prefix from model_name.
    """
    responses = DummyResponses()

    class DummyClient:
        def __init__(self, *args, **kwargs):
            self.responses = SimpleNamespace(create=responses.create)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_: None))

    monkeypatch.setattr(llm_providers, "OpenAI", DummyClient)

    provider = OpenAIProvider(
        api_key="test-openai-key",
        config={
            "name": "test-model",
            "model_name": "openai/gpt-5.1-codex-mini",
            "provider": "openai",
            "trueskill_mu": 30.0,
            "trueskill_sigma": 2.5,
            "trueskill_exposed": 25.0,
        },
    )

    provider.get_response("Say UP")

    assert responses.last_kwargs is not None, "Expected a responses.create call"
    assert responses.last_kwargs.get("model") == "gpt-5.1-codex-mini"

    input_payload = responses.last_kwargs.get("input")
    assert isinstance(input_payload, list)
    assert input_payload[0].get("role") == "user"
    assert isinstance(input_payload[0].get("content"), list)
    assert input_payload[0]["content"][0]["type"] == "input_text"

    for forbidden_key in ("trueskill_mu", "trueskill_sigma", "trueskill_exposed"):
        assert forbidden_key not in responses.last_kwargs
