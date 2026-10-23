# Product clarity implementation log

## Completed
- [x] Audited the provider and candidate-generation flow: the LLM SDK response was plain text; the application expected a strict JSON array and fell back to deterministic candidates after parse failure.
- [x] Added a JSON Schema to generation requests and enabled strict JSON Schema response mode in the Groq and NVIDIA OpenAI-compatible adapters. Kept bounded JSON parsing and per-candidate domain validation after the provider response.
- [x] Clarified experiment result cards with LLM/fallback/deterministic verdicts and plain-language meanings for execution outcomes.
- [x] Added test-by-test explanation scaffolding, exact request and expected behavior labels, and a redacted response label in expanded run evidence.
- [x] Added styled hover/focus tooltips for collapsed sidebar icon labels and accessible aria-labels.

## In progress
- [ ] Add the report setup/run flow simplifications and compact visual summary.
- [ ] Verify frontend typecheck/build and focused backend tests; fix any issues.
- [ ] Update this log with verification results and remaining limitations.

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
- Focused pytest suite — not run: host Python has no pytest installed, and Docker API access was denied by the environment.

### Remaining work
- Add compact pictographic report visualization and a guided, lower-friction setup/run flow.
- Run backend tests in an environment with project API dependencies available and confirm real configured-provider structured-output compatibility.
- Inspect the UI in the browser at narrow and wide widths.
- Final `npm run typecheck --prefix apps/web` after report-guide styling — passed.
