import os
from openai import OpenAI
import anthropic
from google import genai
from google.genai import types
from typing import Dict, Any, Optional
from together import Together
from ollama import chat
from ollama import ChatResponse

class LLMProviderInterface:
    """
    A common interface for LLM calls.
    Model name is stored during initialization.
    """
    def get_response(self, prompt: str) -> str: # Removed model parameter
        raise NotImplementedError("Subclasses should implement this method.")

    @staticmethod
    def extract_api_kwargs(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts fields not part of the standard internal configuration
        into a dictionary suitable for passing as kwargs to the underlying API call.
        """
        api_kwargs = {}
        # Fields used internally for setup, not passed to the API directly
        known_fields = {'name', 'provider', 'pricing', 'kwargs', 'model_name', 'api_type'}

        # Start with any explicitly defined 'kwargs' from the config
        api_kwargs.update(config.get('kwargs', {}))

        # Add any other top-level fields that aren't known internal fields
        for field_name, value in config.items():
            if field_name not in known_fields:
                api_kwargs[field_name] = value

        return api_kwargs

class OpenAIProvider(LLMProviderInterface):
    def __init__(self, api_key: str, config: Dict[str, Any]):
        self.client = OpenAI(api_key=api_key)
        self.model_name = config['model_name'] # Store model name
        # Store config values needed specifically by this provider
        self.api_type = config.get('api_type', 'completions')
        # Extract and store only the kwargs intended for the API call
        self.api_kwargs = self.extract_api_kwargs(config)

    def get_response(self, prompt: str) -> str: # Removed model parameter
        if self.api_type == 'responses':
            # Assuming 'responses' API takes different args, adjust if needed
            # For now, let's pass the extracted kwargs here too.
            response = self.client.responses.create(
                model=self.model_name, # Use stored model name
                input=prompt,
                **self.api_kwargs,
            )
            # Adjust response parsing based on the actual API structure
            return response.output_text.strip() # Example, might need change
        else: # Default to chat completions
            response = self.client.chat.completions.create(
                model=self.model_name, # Use stored model name
                messages=[{"role": "user", "content": prompt}],
                **self.api_kwargs,
            )
            return response.choices[0].message.content.strip()


class AnthropicProvider(LLMProviderInterface):
    def __init__(self, api_key: str, config: Dict[str, Any]):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model_name = config['model_name'] # Store model name
        self.api_kwargs = self.extract_api_kwargs(config)

    def get_response(self, prompt: str) -> str: # Removed model parameter
        response = self.client.messages.create(
            model=self.model_name, # Use stored model name
            messages=[{"role": "user", "content": prompt}],
            **self.api_kwargs,
        )
        return response.content[0].text.strip()


class GeminiProvider(LLMProviderInterface):
    def __init__(self, api_key: str, config: Dict[str, Any]):
        self.client = genai.Client(api_key=api_key)
        self.model_name = config['model_name']
        self.api_kwargs = self.extract_api_kwargs(config)

    def get_response(self, prompt: str) -> str: # Removed model parameter
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(**self.api_kwargs)
        )
        return response.text.strip()


class TogetherProvider(LLMProviderInterface):
    def __init__(self, api_key: str, config: Dict[str, Any]):
        self.client = Together(api_key=api_key)
        self.model_name = config['model_name'] # Store model name
        self.api_kwargs = self.extract_api_kwargs(config)

    def get_response(self, prompt: str) -> str: # Removed model parameter
        response = self.client.chat.completions.create(
            model=self.model_name, # Use stored model name
            messages=[{"role": "user", "content": prompt}],
            **self.api_kwargs,
        )
        return response.choices[0].message.content.strip()

class OllamaProvider(LLMProviderInterface):
    def __init__(self, url: str = "http://localhost:11434", config: Dict[str, Any] = None):
        self.url = url
        # Ensure config is not None before extracting kwargs
        self.api_kwargs = self.extract_api_kwargs(config) if config else {}
        # Store model name, removing prefix if present
        raw_model_name = config['model_name'] if config else 'unknown'
        self.model_name = raw_model_name[len("ollama-"):] if raw_model_name.lower().startswith("ollama-") else raw_model_name


    def get_response(self, prompt: str) -> str: # Removed model parameter
        # Pass options dictionary if present in kwargs, otherwise pass kwargs directly
        options = self.api_kwargs.pop('options', None) if self.api_kwargs else None
        if options:
             response: ChatResponse = chat(model=self.model_name, messages=[ # Use stored model name
                {
                    'role': 'user',
                    'content': prompt,
                },
            ], options=options, **self.api_kwargs)
        else:
             response: ChatResponse = chat(model=self.model_name, messages=[ # Use stored model name
                {
                    'role': 'user',
                    'content': prompt,
                },
            ], **self.api_kwargs)

        # Ensure response format is handled correctly (might vary based on ollama lib version)
        if isinstance(response, dict) and 'message' in response and 'content' in response['message']:
             return response['message']['content'].strip()
        elif hasattr(response, 'message') and hasattr(response.message, 'content'):
             return response.message.content.strip()
        else:
             print(f"Unexpected Ollama response format: {response}")
             return "" # Or raise an error


def create_llm_provider(player_config: Dict[str, Any]) -> LLMProviderInterface:
    """
    Factory function for creating an LLM provider instance.
    Uses the 'provider' key in player_config to determine which class to instantiate.
    """
    provider = player_config['provider']

    if provider == 'openai':
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is not set in the environment variables.")
        return OpenAIProvider(api_key=os.getenv("OPENAI_API_KEY"), config=player_config)
    elif provider == 'anthropic':
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY is not set in the environment variables.")
        return AnthropicProvider(api_key=os.getenv("ANTHROPIC_API_KEY"), config=player_config)
    elif provider == 'google':
        if not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("GOOGLE_API_KEY is not set in the environment variables.")
        return GeminiProvider(api_key=os.getenv("GOOGLE_API_KEY"), config=player_config)
    elif provider == 'ollama':
        # Make sure config is passed for Ollama as well
        return OllamaProvider(url=os.getenv("OLLAMA_URL", "http://localhost:11434"), config=player_config)
    elif provider == 'together':
        if not os.getenv("TOGETHERAI_API_KEY"):
            raise ValueError("TOGETHERAI_API_KEY is not set in the environment variables.")
        return TogetherProvider(api_key=os.getenv("TOGETHERAI_API_KEY"), config=player_config)
    else:
        raise ValueError(f"Unsupported provider: {provider}")
