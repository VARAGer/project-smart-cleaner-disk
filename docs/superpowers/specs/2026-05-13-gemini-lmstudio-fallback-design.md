# Gemini Primary With LM Studio Fallback - Design

## Goal

Add a resilient AI analysis path to the backend where Gemini remains the primary provider and a local LM Studio server running `Qwen3.5-9B` is used only as a fallback when Gemini cannot produce a usable classification response.

## Context

The project keeps a strict ownership split:

- The client owns scanning, filtering, grouping, local SQLite storage, and file deletion.
- The backend owns authentication and AI proxying only.
- The backend must not receive file contents or full local paths.

The current backend already follows this boundary. It receives file metadata, calls Gemini or Groq, validates classifications, and falls back to default classifications if the AI path fails. The target design keeps the same API contract and changes only the provider strategy inside `server/`.

## Final Provider Strategy

### Primary provider

Gemini 1.5 Flash stays the default and primary AI provider.

### Fallback provider

LM Studio becomes a local fallback provider using `Qwen3.5-9B` served through LM Studio's OpenAI-compatible API.

### Removed provider

Groq is removed from the active production flow and from normal configuration examples. The fallback chain should have exactly three stages:

1. Gemini
2. LM Studio
3. Backend-generated default classifications

## Why `Qwen3.5-9B`

`Qwen3.5-9B` is the selected local fallback model because it fits the target hardware profile of `16 GB VRAM / 32 GB RAM` more conservatively than larger alternatives while still providing:

- A native long context window large enough for backend metadata batches.
- Apache 2.0 licensing.
- Strong instruction-following and long-context characteristics for structured classification prompts.

The design intentionally excludes heavier local alternatives. If the local model is later upgraded, the backend integration should remain unchanged as long as LM Studio continues exposing an OpenAI-compatible endpoint.

## Failure Semantics

Fallback to LM Studio must occur not only for network or HTTP failures from Gemini, but also when Gemini returns a response that is not usable for the application.

LM Studio fallback is triggered when Gemini:

- Times out.
- Returns an HTTP error.
- Returns malformed JSON.
- Returns JSON that cannot be parsed into the expected classification structure.
- Returns data that fails server-side completeness or structure checks for the requested batch.

If LM Studio also fails or returns an unusable response, the backend returns default classifications for every requested file, preserving the current endpoint contract and avoiding HTTP 500 responses.

## Backend Architecture

### Configuration

`server/config.py` should evolve toward:

- `AI_PROVIDER=gemini`
- `AI_ENABLE_LOCAL_FALLBACK=true`
- `LM_STUDIO_BASE_URL`
- `LM_STUDIO_MODEL`
- `LM_STUDIO_TIMEOUT_SECONDS`

The Docker-oriented default for the local fallback should point at the host machine, not the backend container itself:

- Native backend execution: `http://127.0.0.1:1234/v1`
- Backend in Docker on Windows/macOS: `http://host.docker.internal:1234/v1`

Groq-related runtime configuration should be removed from the normal path.

### AI Service Flow

`server/services/ai_service.py` should own the complete fallback chain:

1. Build the prompt once from metadata.
2. Call Gemini.
3. Parse and validate the Gemini response.
4. If Gemini fails functionally or technically, log the provider transition and call LM Studio.
5. Parse and validate the LM Studio response with the same application-level checks.
6. If both providers fail, return backend defaults.

The endpoint contract must not change.

## LM Studio Request Contract

LM Studio should be called through:

- `POST /v1/chat/completions`
- OpenAI-compatible messages format
- A model ID provided by `LM_STUDIO_MODEL`
- Structured output via `response_format=json_schema`

The JSON schema should enforce the outer response structure:

- top-level object with `classifications`
- every item has `file_id`, `confidence`, `category`, and `reason`

Because `Qwen3.5` operates in thinking mode by default, the LM Studio request should explicitly disable that mode with:

- `chat_template_kwargs.enable_thinking=false`

The backend should keep a low temperature and preserve all existing post-processing safeguards after model generation.

## Validation Strategy

Provider output validation has two layers:

1. **Format-level validation**
   - Response must be JSON.
   - Response must expose a classification collection in the expected shape.

2. **Application-level validation**
   - Every requested `file_id` must be represented in the final result.
   - No unexpected file IDs should be trusted.
   - Confidence must stay in `[0.0, 1.0]`.
   - Missing or invalid fields must not silently pass as a success path for the primary provider.

The implementation may still normalize malformed individual fields after a provider response is accepted, but a provider should not be considered successful if the overall batch is structurally broken or incomplete.

## Logging

Logs should help diagnose fallback behavior without exposing sensitive request payloads.

Expected logging events:

- Gemini request failed technically.
- Gemini response rejected as unusable.
- LM Studio fallback started.
- LM Studio fallback failed technically or functionally.
- Default classifications returned after both providers fail.

Logs must avoid:

- Prompt content.
- Raw response bodies.
- Full metadata payloads.
- User filenames or parent directories.

## Files Expected To Change

- `server/config.py`
- `server/services/ai_service.py`
- `server/tests/test_ai_service.py`
- `.env.example`
- `server/docker-compose.yml`
- documentation under `docs/`

## Testing Scope

Testing is split into two layers.

### Layer 1 - deterministic backend tests

Unit and mocked integration coverage should prove:

1. Gemini success short-circuits the fallback path.
2. Gemini technical failure triggers LM Studio.
3. Gemini malformed JSON triggers LM Studio.
4. Gemini structurally unusable JSON triggers LM Studio.
5. LM Studio success returns validated classifications.
6. LM Studio failure falls through to backend defaults.
7. Existing API-level behavior remains stable for `/api/analyze`.

These tests must stay fast, deterministic, and independent from real network
or local model availability.

### Layer 2 - real-provider evaluation runs

The repository already contains deterministic seeded file generators in
`server/tests/factories.py`. The implementation plan should add an opt-in
evaluation harness that reuses those generators to exercise the real providers
directly.

The evaluation harness should:

- Produce at least two large deterministic batches, each containing `200`
  files.
- Send the exact same generated batches to Gemini and to LM Studio.
- Validate the returned payloads automatically:
  - JSON parses successfully.
  - Expected top-level structure exists.
  - Every requested `file_id` appears exactly once.
  - No unexpected `file_id` is returned.
  - `confidence` is within `[0.0, 1.0]`.
  - `category` belongs to the allowed category set.
  - `reason` is non-empty.
- Persist raw provider responses and normalized validation summaries as local
  evaluation artifacts for manual review.

These real-provider runs should be explicit developer-invoked checks rather
than mandatory CI gates, because they depend on external API/network state and
on a locally running LM Studio server.

### Semantic review

Structural validity does not fully prove classification quality. After the real
provider runs, the resulting JSON payloads can be reviewed manually to compare
Gemini and LM Studio on:

- Overconfident deletion recommendations.
- Incorrect or weak category selection.
- Reasons that are syntactically valid but semantically unhelpful.
- Stability on ambiguous or borderline files.

The design assumes that this semantic review may be performed outside the
automated test runner when needed.

## Non-Goals

- Replacing Gemini as the primary provider.
- Exposing provider choice to the client.
- Moving AI analysis onto the client.
- Sending file contents to any backend or model provider.
- Supporting larger local models as a separate product mode.
- Implementing model orchestration outside the backend provider flow.

## Expected Outcome

After implementation, the backend will preserve the current external API while becoming more resilient:

- Gemini remains the default online analysis engine.
- LM Studio provides a local rescue path when Gemini cannot produce a usable response.
- Users still receive a stable response contract even if both AI providers fail.
