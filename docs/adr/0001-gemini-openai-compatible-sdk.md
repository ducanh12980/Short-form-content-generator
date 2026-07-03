# 0001. Gemini via OpenAI-compatible SDK

- **Status**: accepted
- **Date**: 2026-07-03
- **Context**: The MVP orchestrator uses the universal `openai` Python SDK. Gemini exposes an OpenAI-compatible REST surface, so one client pattern can target Gemini without a separate SDK.
- **Decision**: Route LLM calls through `OpenAI(api_key=..., base_url=...)` with `OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/` and Gemini model IDs (`SCRIPT_WRITER_MODEL`, `CAPTION_STYLER_MODEL`). Load secrets from `.env` via `python-dotenv` at pipeline start.
- **Consequences**: Model names and base URL must stay aligned with Google's compatible API. Swapping to native OpenAI only requires changing env vars, not orchestrator structure. Provider-specific quirks (e.g. `response_format`) must be validated per model.
