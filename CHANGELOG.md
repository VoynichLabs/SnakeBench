### Version 0.0.2  Dec 11, 2025 (ARC Explainer integration)

- **Changelog alignment with ARC Explainer** (Author: GPT-5.2 Extra High)
  - No SnakeBench-core code changes in this submodule for the Worm Arena Live streaming/Hall of Fame refactor; those changes live in the ARC Explainer repo and are documented in the root `CHANGELOG.md`.
  - This entry exists only to keep integration history consistent across changelogs.

### Version 0.0.1  Dec 12, 2025 (ARC Explainer integration)

- **OpenRouter Responses defaults for OpenAI/xAI models** (Author: Cascade)
  - When using OpenRouter models under the `openai/*` or `x-ai/*` namespaces with the Responses API, SnakeBench now enforces reasoning-friendly defaults to avoid runs that incur reasoning tokens but return no captured reasoning artifacts.
  - Defaults enforced (when missing): `reasoning.summary: "detailed"`, `text.verbosity: "medium"`, `store: true`, and `include: ["reasoning.encrypted_content"]`.
  - **Files Modified**: `backend/llm_providers.py`
