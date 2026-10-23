# Product clarity implementation log

## Completed
- [x] Audited the provider and candidate-generation flow: the LLM SDK response was plain text; the application expected a strict JSON array and fell back to deterministic candidates after parse failure.
- [x] Added a JSON Schema to generation requests and enabled strict JSON Schema response mode in the Groq and NVIDIA OpenAI-compatible adapters. Kept bounded JSON parsing and per-candidate domain validation after the provider response.
- [x] Clarified experiment result cards with LLM/fallback/deterministic verdicts and plain-language meanings for execution outcomes.
- [x] Added test-by-test explanation scaffolding, exact request and expected behavior labels, and a redacted response label in expanded run evidence.
- [x] Added styled hover/focus tooltips for collapsed sidebar icon labels and accessible aria-labels.

## In progress
- [ ] Add the report setup/run flow simplifications and compact visual summary.
- [x] Verify frontend, backend, provider integration, and runtime health; fix issues found.
- [x] Record verification results and remaining limitations in this log.

## Known limitations
- Provider structured-output support varies by model. Unsupported model/provider combinations should surface as provider errors; application parsing and candidate validation remain the safety boundary.
- HTTP request completion is not equivalent to passing a semantic assertion; current report language preserves that distinction.
## 2026-10-23 — LLM response and report clarity

- Audited the LLM path: configured providers were asked for free-form text, while candidate generation required a bounded JSON array; malformed output caused the completed run to fall back silently among its saved candidates.
- LLM generation now requests strict JSON Schema output from the OpenAI-compatible Groq and NVIDIA adapters. The existing bounded JSON parser, OpenAPI parameter checks, and domain candidate validation still run on returned content.
- Added provider adapter tests asserting that the JSON Schema response format is sent when the request includes a schema.
- Experiment approach cards now say whether LLM candidates, deterministic fallback candidates, or a deterministic-only policy were used, and summarize observed request outcomes without claiming that HTTP completion proves correctness.
- Expanded run evidence with a short guide, understandable generated-test provenance labels, explicit request/expected-behavior/response headings, and per-test explanation of the result.
- Added a report-reading guide explaining candidates, executed requests, correctness checks, and N/A metric reasons.
- Added styled hover and keyboard-focus tooltips plus accessible labels for collapsed sidebar links.
- Added this completion log at `docs/PRODUCT_CLARITY_IMPLEMENTATION_LOG.md`.

### Verification
- `npm run typecheck --prefix apps/web` — passed.
- `npm run build --prefix apps/web` — passed.
- `git diff --check` — passed; Git displayed only line-ending normalization notices.
- Focused pytest suite — later run in the API container; 38 passed.

### Remaining work
- Add compact pictographic report visualization and a guided, lower-friction setup/run flow.
- Inspect the UI in the browser at narrow and wide widths.
- Final `npm run typecheck --prefix apps/web` after report-guide styling — passed.

## 2026-10-23 — Groq provider 400 audit and smoke verification

- Captured a live Groq response using the configured `openai/gpt-oss-120b` key without printing or persisting the credential. A deliberately small 100-token diagnostic returned HTTP 400 with provider code `json_validate_failed`, message `Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.`, and an empty `failed_generation` value.
- Retried with the application's 1,200-token generation budget and corrected strict schema: Groq returned valid schema-conforming JSON (526 total tokens in the direct request).
- Exercised the complete app generation path against a synthetic OpenAPI `GET /health` operation: Groq returned five candidates and application parsing/domain validation accepted them.
- Repaired the strict schema contract: it now has a closed object root, schema objects disallow undeclared properties, and arbitrary OpenAPI parameter/body objects are encoded as JSON strings and parsed/validated locally. The app asks for the matching `{ "candidates": [...] }` envelope.
- Groq HTTP errors now retain the provider's bounded error code/message after credential scrubbing. `json_validate_failed`, request/schema 400s, and `blocked_api_access` spend-limit 400s are distinguished in run diagnostics.
- Smoke testing exposed and fixed two related correctness issues: the legacy preview marked malformed JSON as LLM success; deterministic-only approaches reported an LLM candidate-validity score. Both now report accurate outcomes.

### Smoke verification
- Focused provider/candidate/approach tests — 38 passed.
- Full API pytest suite — 253 passed, 6 upstream/framework deprecation warnings.
- Backend Ruff — passed.
- Backend mypy — passed for 107 source files.
- Frontend typecheck and production build — passed.
- Frontend ESLint — passed with 3 existing Fast Refresh warnings.
- Live provider candidate-generation request — 5 valid candidates.
- Compose API, worker, database, and web containers — running; API and database healthy.
- `GET http://localhost:8000/health/ready` — returned `{"status":"ready"}`.
- `GET http://localhost:5173` — returned HTTP 200.

### Diagnostic limitation
- The screenshot's original historical response body was not retained by the previous adapter, so that exact provider message cannot be reconstructed. The captured live reproduction proves the `json_validate_failed` path; with the app's real token budget and repaired schema, the same provider/model succeeds.

## 2026-10-23 — Bounded Groq generation and fallback diagnostics

- Confirmed the configured default model is `openai/gpt-oss-120b`. The outgoing candidate schema has a closed object root and candidate object, requires all five contract fields, and uses the documented nullable string union for `body_json`. Groq's current strict-output documentation lists this model and accepts the schema's required/closed-object/nullability pattern.
- Replaced the vague 50-candidate prompt with an experiment-configurable limit of 1–10 candidates per operation (UI offers 3–5; default 4). The prompt asks for no more than that count and forbids inventing unsupported behavior. Output tokens scale by count and remain capped at 1,200.
- Bounded Semantic assisted context to 12 per-operation extracted parameter/body/response facts, at 4 KiB each. Inferred facts, security requirement facts, invalid JSON values, and unrecognized fact types are excluded.
- Groq provider errors now retain HTTP status, provider code/message, model, retryability, and a credential-scrubbed `failed_generation` excerpt capped at 512 characters. Diagnostics include attempt, retry scheduling, timeout/token limits, completion receipt, and local parse/validation outcome. Raw prompts, credentials, and raw completion bodies are not logged.
- Added at most three configurable total attempts (`LLM_GENERATION_MAX_ATTEMPTS`, default 2) with exponential jitter for transient timeouts/connections, 429s, and 5xx errors. Deterministic 400/schema failures are not retried. The SDK retry is disabled so retry counts remain auditable.
- Persisted generation errors, retry count, attempt count, requested/accepted/rejected counts, fallback marker, per-test source, and generation/validation timing. API run and experiment responses now expose `completed_with_fallback` when campaign execution completed using deterministic fallback. The UI shows fallback state, request budget, and bounded provider diagnostics.
- Runs with no executable candidates are now persisted as failed campaigns and surfaced as `generation_failed` in experiment responses, rather than raising before the diagnostics can be committed.
- Exact historical root cause remains unconfirmed: earlier run records had no `failed_generation` detail, so the rejected content cannot be recovered. The current schema/request contract is verified against live Groq and is not inherently rejected by the configured model.

### Verification
- Mocked Groq, prompt/validation, approach/fallback, semantic-context, retry, truncation, and status tests: 37 passed.
- Ruff on changed backend files: passed.
- Mypy on changed backend source areas: passed (18 source files).
- Frontend TypeScript typecheck, ESLint on touched experiment files, and production build: passed.
- Live Groq checks using the configured model: minimal strict JSON succeeded (77 completion tokens); actual IntelAPI candidate schema on a synthetic `GET /health` operation succeeded with 1 accepted candidate (449 completion tokens); the same operation with one extracted semantic fact succeeded with 2 accepted candidates (510 completion tokens). No credential was printed.
- Live test limitation: Docker engine was unavailable, so the running browser/API stack and full database-backed experiment persistence path could not be verified in this turn. Three existing database-backed experiment API tests could not complete fixture setup because PostgreSQL at localhost:5432 was unavailable; the focused non-database unit set passed.
