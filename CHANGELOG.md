<!--
Author: GPT-5
Date: 2025-12-25
PURPOSE: SnakeBench changelog for ARC Explainer integration updates.
SRP/DRY check: Pass - entries track external changes only.
-->

### Version 0.0.4  Dec 27, 2025 (ARC Explainer integration)

- **Prompt: Disable web search for LLM players** (Author: Claude Sonnet 4.5)
  - Added explicit instruction to prevent models from performing web searches during gameplay.
  - Ensures models only use the provided game state without accessing external information.
  - **Files Modified**: `backend/players/llm_player.py:187`, `backend/players/llm_player_a.py:198`

### Version 0.0.3  Dec 25, 2025 (ARC Explainer integration)

- **Fix: OpenRouter transforms routing for Worm Arena** (Author: GPT-5)
  - OpenRouter-only `transforms` are routed through `extra_body` to avoid OpenAI SDK errors.
  - OpenAI direct calls strip `transforms` entirely.
  - **Files Modified**: `backend/llm_providers.py`, `README.md`

### Version 0.0.2  Dec 11, 2025 (ARC Explainer integration)

- **Changelog alignment with ARC Explainer** (Author: GPT-5.2 Extra High)
  - No SnakeBench-core code changes in this submodule for the Worm Arena Live streaming/Hall of Fame refactor; those changes live in the ARC Explainer repo and are documented in the root `CHANGELOG.md`.
  - This entry exists only to keep integration history consistent across changelogs.

### Version 0.0.1  Dec 12, 2025 (ARC Explainer integration)

- **OpenRouter Responses defaults for OpenAI/xAI models** (Author: Cascade)
  - When using OpenRouter models under the `openai/*` or `x-ai/*` namespaces with the Responses API, SnakeBench now enforces reasoning-friendly defaults to avoid runs that incur reasoning tokens but return no captured reasoning artifacts.
  - Defaults enforced (when missing): `reasoning.summary: "detailed"`, `text.verbosity: "medium"`, `store: true`, and `include: ["reasoning.encrypted_content"]`.
  - **Files Modified**: `backend/llm_providers.py`
