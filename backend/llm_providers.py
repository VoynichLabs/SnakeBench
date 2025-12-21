import os
import json
from json.decoder import JSONDecodeError
from openai import OpenAI
from typing import Dict, Any, Optional, List, Tuple, Union


def _sanitize_env_value(value: Optional[str]) -> Optional[str]:
    """
    Clean up env-provided strings that may include surrounding quotes or whitespace.

    Some shells/export flows set values like OPENROUTER_API_KEY="sk-or-...".
    The OpenAI SDK forwards the raw string, so we strip wrapping quotes here
    to avoid 401s that look like "No cookie auth credentials found".
    """
    if value is None:
        return None
    cleaned = value.strip()
    if len(cleaned) >= 2 and (
        (cleaned[0] == '"' and cleaned[-1] == '"') or (cleaned[0] == "'" and cleaned[-1] == "'")
    ):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _normalize_provider_name(value: Optional[str]) -> str:
    if not value:
        return ""
    return str(value).strip().lower()


def _normalize_openai_model_name(model_name: str) -> str:
    """
    Allow SnakeBench configs that use OpenRouter-style namespaces like "openai/gpt-5.1-codex"
    while still calling OpenAI directly with the native model id (e.g. "gpt-5.1-codex").
    """
    if not model_name:
        return model_name
    cleaned = str(model_name).strip()
    if cleaned.startswith("openai/"):
        return cleaned[len("openai/") :]
    return cleaned


def _build_responses_input(prompt: str) -> List[Dict[str, Any]]:
    """
    Build a Responses API compliant input payload (role/content items, not chat messages).
    """
    return [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
            ],
        }
    ]


def _extract_text_from_responses_output(response: Any, *, provider_label: str) -> Tuple[str, int, int]:
    """
    Extract (text, input_tokens, output_tokens) from an OpenAI Responses-like payload.

    Supports both SDK objects and dict-like payloads. This logic is shared by OpenRouter
    (proxy) and direct OpenAI providers.
    """
    output = getattr(response, "output", None)
    if output is None and isinstance(response, dict):
        output = response.get("output")
    if not output:
        raise ValueError(f"{provider_label} response missing output field: {response}")

    text = None
    for item in output:
        content = getattr(item, "content", None)
        if content is None and isinstance(item, dict):
            content = item.get("content")
        if not content:
            continue

        for block in content:
            block_type = getattr(block, "type", None)
            if block_type is None and isinstance(block, dict):
                block_type = block.get("type")

            block_text = getattr(block, "text", None)
            if block_text is None and isinstance(block, dict):
                block_text = block.get("text")

            if block_text and (block_type in {None, "output_text", "text"}):
                text = block_text
                break

        if text:
            break

    if text is None:
        text = getattr(response, "output_text", None)

    if not text:
        raise ValueError(f"{provider_label} response missing text content: {output}")

    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage", {})

    input_tokens = getattr(usage, "input_tokens", 0) if usage else 0
    output_tokens = getattr(usage, "output_tokens", 0) if usage else 0

    return str(text or "").strip(), int(input_tokens or 0), int(output_tokens or 0)


class LLMProviderInterface:
    """
    A common interface for LLM calls.
    Model name is stored during initialization.
    """
    def get_response(self, prompt: str) -> Dict[str, Any]: # Returns dict with response and usage
        raise NotImplementedError("Subclasses should implement this method.")

    def health_check(self) -> bool:
        """
        Check if the model is available and accessible.
        Returns True if model is available, False otherwise.
        """
        raise NotImplementedError("Subclasses should implement this method.")

    @staticmethod
    def extract_api_kwargs(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts fields not part of the standard internal configuration
        into a dictionary suitable for passing as kwargs to the underlying API call.
        """
        api_kwargs = {}
        # Fields used internally for setup, not passed to the API directly
        # Includes both legacy YAML fields and database fields from Supabase
        known_fields = {
            'name', 'provider', 'pricing', 'kwargs', 'model_name', 'api_type',
            # Database fields from Supabase models table
            'id', 'model_slug', 'is_active', 'test_status', 'elo_rating', 'rating',
            'wins', 'losses', 'ties', 'apples_eaten', 'games_played',
            'pricing_input', 'pricing_output', 'max_completion_tokens',
            'last_played_at', 'discovered_at'
        }

        # Start with any explicitly defined 'kwargs' from the config
        api_kwargs.update(config.get('kwargs', {}))

        # Add any other top-level fields that aren't known internal fields
        for field_name, value in config.items():
            # Filter out rating/metadata fields that shouldn't reach the API
            if field_name in known_fields or field_name.startswith("trueskill_"):
                continue
            api_kwargs[field_name] = value

        return api_kwargs

class OpenRouterProvider(LLMProviderInterface):
    def __init__(self, api_key: str, config: Dict[str, Any]):
        raw_base_url = os.getenv("OPENROUTER_BASE_URL")
        base_url = _sanitize_env_value(raw_base_url) or "https://openrouter.ai/api/v1"
        self.client = OpenAI(api_key=_sanitize_env_value(api_key) or api_key, base_url=base_url)
        self.model_name = config['model_name']
        self.api_type = config.get('api_type', 'completions')
        self.api_kwargs = self.extract_api_kwargs(config)

        explicit_headers = self.api_kwargs.pop('extra_headers', None)
        env_headers = {}
        referer = os.getenv("OPENROUTER_SITE_URL", "https://snakebench.com")
        title = os.getenv("OPENROUTER_SITE_NAME", "SnakeBench")
        if referer:
            env_headers["HTTP-Referer"] = referer
        if title:
            env_headers["X-Title"] = title
        if explicit_headers:
            env_headers.update(explicit_headers)
        self.extra_headers = env_headers or None

    def get_response(self, prompt: str) -> Dict[str, Any]:
        request_kwargs = dict(self.api_kwargs)
        if self.extra_headers:
            request_kwargs['extra_headers'] = self.extra_headers

        # Add middle-out transform for automatic context compression (OpenRouter feature)
        # This helps prevent context overflow by intelligently compressing the prompt
        if 'transforms' not in request_kwargs:
            request_kwargs['transforms'] = ['middle-out']

        if self.api_type == 'responses':
            if self.model_name.startswith("openai/") or self.model_name.startswith("x-ai/"):
                reasoning = request_kwargs.get("reasoning")
                if not isinstance(reasoning, dict):
                    reasoning = {}
                if "effort" not in reasoning:
                    reasoning["effort"] = "medium"
                if "summary" not in reasoning:
                    reasoning["summary"] = "detailed"
                request_kwargs["reasoning"] = reasoning

                text = request_kwargs.get("text")
                if not isinstance(text, dict):
                    text = {}
                if "verbosity" not in text:
                    text["verbosity"] = "medium"
                request_kwargs["text"] = text

                # OpenRouter's Responses API schema rejects store=true for proxied OpenAI/xAI models.
                # Allow the request to proceed by omitting store entirely (or forcing false).
                if "store" in request_kwargs:
                    request_kwargs.pop("store", None)

                include = request_kwargs.get("include")
                if include is None:
                    include = []
                if isinstance(include, str):
                    include = [include]
                if not isinstance(include, list):
                    include = []
                if "reasoning.encrypted_content" not in include:
                    include.append("reasoning.encrypted_content")
                request_kwargs["include"] = include

            # Add max output tokens to prevent runaway generation
            # This prevents models from generating 400k+ token rationales
            if 'max_output_tokens' not in request_kwargs:
                request_kwargs['max_output_tokens'] = 16000

            response = self.client.responses.create(
                model=self.model_name,
                input=_build_responses_input(prompt),
                **request_kwargs,
            )
            if isinstance(response, str):
                try:
                    response = json.loads(response)
                except json.JSONDecodeError:
                    preview = response[:200].replace('\n', ' ')
                    raise ValueError(f"OpenRouter returned unexpected text payload: {preview}...")

            text, input_tokens, output_tokens = _extract_text_from_responses_output(
                response, provider_label="OpenRouter"
            )

            return {
                "text": text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        else:
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    **request_kwargs,
                )
            except JSONDecodeError as exc:
                raise ValueError(
                    "OpenRouter chat completion returned a non-JSON payload. "
                    "This usually means the model slug is invalid or the request was redirected to an HTML error page."
                ) from exc

            # Extract usage information
            usage = response.usage if hasattr(response, 'usage') else None

            return {
                "text": response.choices[0].message.content.strip(),
                "input_tokens": usage.prompt_tokens if usage else 0,
                "output_tokens": usage.completion_tokens if usage else 0
            }

    def health_check(self) -> bool:
        """
        Check if the model is available on OpenRouter.
        Makes a minimal API call to verify the model exists and is accessible.
        Returns True if model is available, False if it returns a 404 or other error.
        """
        try:
            request_kwargs = dict(self.api_kwargs)
            if self.extra_headers:
                request_kwargs['extra_headers'] = self.extra_headers

            # Override max_tokens to 1 for minimal cost
            request_kwargs['max_tokens'] = 1

            # Make a minimal test request
            if self.api_type == 'responses':
                response = self.client.responses.create(
                    model=self.model_name,
                    input="test",
                    **request_kwargs,
                )
            else:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": "test"}],
                    **request_kwargs,
                )

            # If we got here without exception, the model is available
            return True

        except Exception as e:
            error_str = str(e).lower()
            # Check for 404 or "model not found" errors
            if '404' in error_str or 'model not found' in error_str or 'not found' in error_str:
                return False
            # For other errors, we'll assume the model might be temporarily unavailable
            # but not necessarily non-existent, so return True to allow retry
            print(f"Warning: Health check failed with non-404 error: {e}")
            return True


class OpenAIProvider(LLMProviderInterface):
    """
    Direct OpenAI provider using the Responses API.

    Uses OPENAI_API_KEY and calls /v1/responses via the official OpenAI SDK.
    """

    def __init__(self, api_key: str, config: Dict[str, Any]):
        self.client = OpenAI(api_key=_sanitize_env_value(api_key) or api_key)
        self.model_name = _normalize_openai_model_name(config["model_name"])
        self.api_type = config.get("api_type", "responses")
        self.api_kwargs = self.extract_api_kwargs(config)

    def get_response(self, prompt: str) -> Dict[str, Any]:
        request_kwargs = dict(self.api_kwargs)

        if self.api_type != "responses":
            raise ValueError("Direct OpenAI provider only supports api_type='responses'")

        reasoning = request_kwargs.get("reasoning")
        if not isinstance(reasoning, dict):
            reasoning = {}
        if "effort" not in reasoning:
            reasoning["effort"] = "medium"
        if "summary" not in reasoning:
            reasoning["summary"] = "detailed"
        request_kwargs["reasoning"] = reasoning

        text = request_kwargs.get("text")
        if not isinstance(text, dict):
            text = {}
        if "verbosity" not in text:
            text["verbosity"] = "medium"
        request_kwargs["text"] = text

        # SnakeBench game calls should not store conversation by default.
        # If caller provides store explicitly, honor it.
        if "store" not in request_kwargs:
            request_kwargs["store"] = False

        response = self.client.responses.create(
            model=self.model_name,
            input=_build_responses_input(prompt),
            **request_kwargs,
        )

        text, input_tokens, output_tokens = _extract_text_from_responses_output(
            response, provider_label="OpenAI"
        )

        return {
            "text": text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    def health_check(self) -> bool:
        try:
            request_kwargs = dict(self.api_kwargs)
            request_kwargs["max_output_tokens"] = 1
            if "store" not in request_kwargs:
                request_kwargs["store"] = False

            self.client.responses.create(
                model=self.model_name,
                input=_build_responses_input("test"),
                **request_kwargs,
            )
            return True
        except Exception as e:
            error_str = str(e).lower()
            if "404" in error_str or "model not found" in error_str or "not found" in error_str:
                return False
            print(f"Warning: OpenAI health check failed with non-404 error: {e}")
            return True


def create_llm_provider(player_config: Dict[str, Any]) -> LLMProviderInterface:
    """
    Factory function for creating an LLM provider instance.

    Supports:
    - OpenRouter (default): OPENROUTER_API_KEY + base_url=https://openrouter.ai/api/v1
    - OpenAI direct: OPENAI_API_KEY + /v1/responses
    """
    provider_name = _normalize_provider_name(player_config.get("provider"))
    model_name = str(player_config.get("model_name") or "")
    normalized_model = _normalize_openai_model_name(model_name)

    openai_api_key = _sanitize_env_value(os.getenv("OPENAI_API_KEY"))
    openrouter_api_key = _sanitize_env_value(os.getenv("OPENROUTER_API_KEY"))

    # Explicit provider selection always wins.
    if provider_name in {"openai", "openai direct"}:
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set in the environment variables.")
        return OpenAIProvider(api_key=openai_api_key, config=player_config)

    if provider_name in {"openrouter"}:
        if not openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is not set in the environment variables.")
        return OpenRouterProvider(api_key=openrouter_api_key, config=player_config)

    # Preference rule:
    # If the model is an OpenAI model and an OpenAI key is available, use OpenAI directly.
    # This avoids routing OpenAI traffic through OpenRouter unless explicitly requested.
    if model_name.startswith("openai/") or normalized_model.startswith("gpt-") or normalized_model.startswith("o"):
        if openai_api_key:
            return OpenAIProvider(api_key=openai_api_key, config=player_config)

    # Default to OpenRouter for everything else.
    if not openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY is not set in the environment variables.")

    return OpenRouterProvider(api_key=openrouter_api_key, config=player_config)
