# Gemini 2.5 Flash With Policy Caps - Design

## Goal

Keep the backend AI path single-provider and production-oriented:

- Gemini 2.5 Flash is the only model provider.
- Groq is removed from the active backend flow.
- The prompt becomes stricter about the meaning of `confidence`.
- The backend applies deterministic policy caps after model output so risky classes of files cannot receive over-aggressive deletion confidence.

## Context

The project boundary remains unchanged:

- The client owns scanning, filtering, grouping, local SQLite storage, and file deletion.
- The backend owns authentication and AI proxying only.
- The backend never receives file contents or full local paths.

The manual comparison on the same `200`-file seeded batch showed:

- Gemini 2.5 Flash returned a complete structured response in roughly tens of seconds.
- Local Qwen 3.5 9B returned a structurally usable response but took roughly one and a half hours on the target machine.
- Qwen is therefore rejected as an online backend option.
- Gemini is practical as the sole provider, but its raw confidence values still need stronger guardrails.

## Final Provider Strategy

The backend provider chain becomes:

1. Gemini 2.5 Flash
2. Backend-generated default classifications if Gemini fails technically or returns an unusable response

There is no LM Studio fallback and no Groq fallback in the target design.

## Gemini Request Contract

The backend should use Gemini structured output rather than relying only on prompt discipline.

The request should:

- Target Gemini 2.5 Flash.
- Use `application/json`.
- Include a response schema for:
  - top-level `classifications`
  - `file_id`
  - `confidence`
  - `category`
  - `reason`
- Keep generation temperature low.

Structured output improves syntactic stability, but it does not remove the need for backend validation or business-rule enforcement.

## Prompt Hardening

The system prompt should be revised around these principles:

### Confidence semantics must be explicit

The prompt must state repeatedly and unambiguously:

- `confidence` means probability that deletion is safe.
- `0.0` means "unsafe to delete".
- `1.0` means "almost certainly safe to delete".
- Old age alone must never imply high delete-safety.

### Risky contexts must suppress confidence

The prompt should explicitly penalize:

- `Desktop`
- `Documents`
- `Projects`
- `.git`
- user media folders

Files in those locations should not receive aggressive delete confidence without a very strong signal.

### Categories and deletion confidence are separate concepts

The model should classify by file type, not by folder context:

- `.mp3` remains `media`, even inside `.git`
- `.zip` remains `archive`, even in a project folder
- `.bak` remains `backup`, not `archive`

Folder location affects deletion confidence, not the category label.

### High-confidence rules must be narrower

Examples of signals that may still justify high confidence:

- Office temp files like `~$...`
- obvious `.tmp` files in temp/cache locations
- installers in `Downloads` or explicit temp locations
- old logs in obvious log/cache/temp locations

## Backend Validation And Policy Caps

The backend should separate three concerns:

1. Parse and shape validation.
2. Completeness validation.
3. Policy capping.

### 1. Parse and shape validation

Gemini output must be rejected as unusable if:

- JSON cannot be parsed.
- The expected classification structure is missing.
- Required fields are missing.
- Category is outside the allowed category set.
- `confidence` is missing or not numeric.
- `reason` is empty.

### 2. Completeness validation

Gemini output must be rejected as unusable if:

- Some requested `file_id` values are missing.
- Duplicate `file_id` values exist.
- Unexpected `file_id` values appear.

Rejected output falls through to backend defaults for the entire batch.

### 3. Policy caps

After a structurally valid Gemini response is normalized, backend policy caps must reduce overconfident scores for risky cases.

Initial policy set:

- `document`
  - hard cap `0.80`
  - hard cap `0.35` if filename contains protected keywords such as `thesis`, `diploma`, `contract`, `report`, `project`, `work`, or Russian equivalents
- `archive`
  - hard cap `0.70` outside temp/cache locations
  - hard cap `0.40` inside `Desktop`, `Documents`, `Projects`, or `.git`
- `backup`
  - hard cap `0.60` outside temp/cache/log locations
  - hard cap `0.40` inside `Desktop`, `Documents`, `Projects`, or `.git`
- `config`
  - hard cap `0.40`
- `database`
  - hard cap `0.30`
- `code`
  - hard cap `0.30`
- `media`
  - hard cap `0.30`
  - hard cap `0.15` if filename suggests personal media such as `wedding`, `family`, `birthday`, `photo`
- `other`
  - hard cap `0.20`
- files in risky directories (`Desktop`, `Documents`, `Projects`, `.git`)
  - apply an additional max cap of `0.60`, unless a stricter category-specific cap already applies

These caps are not intended to replace the model. They constrain the model where false positives are costly.

## Logging

Logs should distinguish:

- Gemini technical failure.
- Gemini structured-output validation failure.
- Policy-cap application counts.
- Default classifications returned after provider failure.

Logs must not expose:

- prompt bodies
- raw model outputs
- filenames
- parent directories

## Files Expected To Change

- `server/config.py`
- `server/services/ai_service.py`
- `server/tests/test_ai_service.py`
- `server/tests/integration/test_analysis_integration.py`
- `.env.example`
- `server/docker-compose.yml`
- docs under `docs/`

## Testing Strategy

### Deterministic backend tests

Tests should cover:

1. Gemini 2.5 Flash request payload uses structured output schema.
2. Malformed JSON returns backend defaults.
3. Missing / duplicate / unexpected `file_id` values return backend defaults.
4. Category and reason validation reject malformed model output.
5. Policy caps reduce risky overconfident scores.
6. Safe temp/installer/log scenarios are not over-capped beyond the intended rules.
7. `/api/analyze` keeps the same API contract.

### Real-provider evaluation runs

The existing seeded generator in `server/tests/factories.py` should remain useful for manual Gemini verification.

Recommended practice:

- Generate one or more fixed `200`-file batches.
- Feed them to Gemini 2.5 Flash with the production prompt.
- Save the response.
- Review:
  - structural completeness
  - whether policy caps would reduce the riskiest scores
  - whether prompt revisions improve semantic quality over the previous run

These checks remain developer-invoked rather than mandatory CI.

## Non-Goals

- Local model fallback.
- Groq fallback.
- Client-visible provider selection.
- Sending file contents to the backend.
- Fully automating semantic correctness judging.

## Expected Outcome

The backend becomes simpler and more defensible:

- one production AI provider
- structured Gemini responses
- stricter confidence semantics
- deterministic post-model caps against risky deletion advice
- stable endpoint behavior when Gemini fails
