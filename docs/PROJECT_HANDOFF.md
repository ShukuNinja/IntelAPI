# IntelAPI — Complete Project Handoff

**Purpose:** as-built product and engineering guide for a new maintainer, presenter, or developer.
**Code baseline:** `final-version`, reviewed 2026-10-24.
**Authority:** this document explains the current repository. Where older planning documents describe aspirational behavior, current code and this guide take precedence for statements about what exists today. Update this guide when behavior or architecture changes.

## 1. What IntelAPI is

IntelAPI is a project-scoped API understanding and testing workbench. A user can import an API contract, inspect operations, generate deterministic request candidates, send bounded requests to a real target, compare contract-priority and semantic-guided candidate selection, evaluate explicit assertions and contract observations, organize saved requests, and review persisted reports or campaign runs.

The core claim is **explainable, contract-grounded test selection**: each generated case has a deterministic mutation and rationale; semantic ranking exposes the facts and score components that affected ordering. This is a research prototype and workflow product. It is not an autonomous vulnerability scanner, a formal OpenAPI conformance proof, or an LLM-based testing agent. Its semantic engine is deterministic rules over contract text and schema; it does not use embeddings, an LLM, a trained model, or runtime production telemetry.

An unusual response, failed assertion, HTTP error status, or schema mismatch is an **observation**. It is not automatically a confirmed defect. A human reviews the evidence and records a triage classification.

## 2. The end-to-end architecture

```text
Browser: React + TypeScript + Vite
  ├── Project context and routed feature pages
  └── JSON API client
          │ /api/v1
          ▼
FastAPI modular monolith
  ├── Project/specification/import routes
  ├── Deterministic candidate generation and experiment ranking
  ├── Shared outbound HTTP execution/security boundary
  ├── Health checks, candidate reports, findings/triage
  ├── Campaign coordinator and report/event routes
  └── SQLAlchemy persistence
          │
          ├──────── PostgreSQL (projects, specs, executions, reports, campaigns)
          │
          └── Separate campaign worker process
                  └── claims durable jobs and invokes campaign execution service
```

This is a **modular monolith**, not a set of microservices. The API and worker are separate processes from the same backend package and share PostgreSQL and execution logic. The browser does not connect directly to the database. Product routes are mounted under `/api/v1`; liveness/readiness routes are `/health/live` and `/health/ready`.

### Main source map

| Concern | Implementation |
|---|---|
| App construction, API route registration | `apps/api/app/main.py`, `apps/api/app/api/router.py` |
| Runtime settings | `apps/api/app/core/config.py` |
| Database session and ORM models | `apps/api/app/db/`, `apps/api/app/models/` |
| Project/specification import and ownership | `apps/api/app/modules/projects/router.py` |
| OpenAPI parse/normalization/candidate rules | `apps/api/app/modules/api_understanding/service.py` |
| Remote spec discovery | `apps/api/app/modules/api_understanding/discovery.py` |
| Shared outbound transport and SSRF checks | `apps/api/app/modules/execution/service.py` |
| Request execution/history and SSRF preflight route | `apps/api/app/modules/execution/router.py` |
| Candidate execution, assertions, contract observations, exports | `apps/api/app/modules/test_generation/router.py` |
| Semantic facts, ranking, run persistence and comparison | `apps/api/app/modules/experiments/semantic.py`, `router.py` |
| Fixed local seeded benchmark API | `apps/api/app/modules/experiments/benchmark.py` |
| Deterministic post-run follow-up decision | `apps/api/app/modules/adaptive/feedback.py` |
| Campaign creation, tests, event report and worker | `apps/api/app/modules/campaigns/` |
| Health check definitions/runs/assertions | `apps/api/app/modules/health_checks/router.py` |
| Observation listing and human triage | `apps/api/app/modules/findings/router.py` |
| Browser routes and navigation | `apps/web/src/app/router.tsx`, `apps/web/src/components/layout/AppShell.tsx` |
| Project switching and selection | `apps/web/src/features/projects/ProjectWorkspaceContext.tsx` |
| Browser feature screens | `apps/web/src/features/` |

## 3. Product workflow and what each feature does

### 3.1 Projects and project context

Projects are the data boundary for specifications, requests, collections, environments, runs, reports, and campaign history. The frontend project context keeps a selected project available across feature pages. The backend checks that referenced resources belong to that project. Local development currently uses a fixed single-user identity; this build does not provide production sign-in or multi-user tenancy.

Project archive is a soft-delete (`deleted_at`), not a hard delete. Historical records are retained in the database.

### 3.2 API Explorer / API understanding

The Explorer can parse OpenAPI 3.0/3.1 and a supported Swagger 2.0 subset, normalize supported operations, save a specification to a project, inspect operations, preview candidate ideas, save generation reports, export reports, and inspect specification readiness.

The parser resolves bounded **local** JSON Pointer `$ref` references. It does not fetch remote `$ref`s. URL discovery is a separate bounded fetch path and must go through outbound target validation. Imported contracts are content-hashed; equivalent imports in a project can reuse a stored spec.

Readiness checks identify documentation/completeness gaps with rule codes and JSON Pointer evidence. Readiness is not runtime validation or a security assessment.

### 3.3 API Workspace

The Workspace sends manually configured HTTP requests through the backend execution boundary, displays the actual status, timing, allowlisted headers, and bounded response body in the active UI, and records minimal project execution history. Users can save named requests, group them in collections, and use project environments for URL/header/body interpolation.

Request bodies may be sent to the selected target. Non-read-only methods require explicit confirmation. A target's HTTP 4xx/5xx is still an `http_response`; it is not the same as a blocked request, timeout, or connection error.

### 3.4 Candidate preview and generation reports

The candidate preview endpoint proposes mutations without calling the target. Generation reports persist deterministic candidate IDs, operation/rule/rationale/mutation information, and coverage/truncation information. A report is a proposal inventory, not an execution log. A candidate's `validation_status: preview` means it has not been sent or validated against runtime behavior.

Current candidate rules are described in section 4.

### 3.5 Candidate execution and execution reports

Users may execute a chosen candidate with baseline values, an expected status, and optional explicit assertions. The backend constructs the request, sends it through the shared execution service, evaluates explicit assertions and a bounded subset of response-contract checks, and persists a report. The response body may be used in memory for checks and returned to the active UI, but is not stored in execution history or candidate reports.

Execution outcomes, assertion outcomes, contract observations, analysis skips, feedback decisions, and next-action advice remain separate fields so one result does not get mistaken for another.

### 3.6 Experimental Workbench

The Workbench runs one or both selection approaches against the same imported specification:

- **Approach A — Contract baseline:** orders the common generated candidate pool using a fixed rule-kind priority and stable operation/candidate IDs.
- **Approach B — Semantic guided:** extracts deterministic facts from the contract, scores candidates using contract coverage, inferred operation intent, resource workflow relationships, and field semantics, then orders by score and stable tie-breakers.

Each approach selects up to the candidate budget. Selected candidates can then be executed against a user-provided base URL, subject to execution budget and unsafe-method confirmation. The results table contains candidate-generation/selection/coverage metrics plus request and assertion results. Run records are persisted and can be reloaded; a comparison export exists when both runs are available.

The semantic fact inspector shows fact type, value, source operation/location, extraction rule/evidence, and evidence strength. It is an explanation of deterministic heuristics, not a natural-language model explanation.

### 3.7 SSRF policy demo

The Workbench's **Run safe SSRF demo** endpoint preflights fixed representative destination addresses with the same syntax and address validator used by outbound execution. It does not send an HTTP request, and the “without protection” column is a description of a simulated vulnerable client, not a switch that disables security.

Current Docker development defaults allow loopback for local testing and block non-global private/reserved destinations. Thus loopback may be allowed by configuration; private, link-local metadata, and reserved demonstration ranges should be blocked. The UI reports the active policy flags and `network_requests_sent: 0`.

### 3.8 Health Checks

Health checks bind to a saved read-only request (`GET`, `HEAD`, or `OPTIONS`) and a list of explicit assertions. A run records the shared execution outcome and assertion results; check definitions and run history can be reopened. Supported assertion families are status, latency threshold, JSON Pointer, allowlisted response header equality, and a bounded response schema check.

### 3.9 Campaigns

Campaigns are created from a persisted generation report and configuration. A campaign creates candidate test cases and a durable job, then a separate worker claims work and records state/progress/events/results. The UI can inspect campaign history, a report and event timeline, and cancel a nonterminal campaign. Execution uses the same outbound boundary. State-changing methods are blocked unless the user explicitly enables them. Missing required baseline data can cause a case to be skipped.

The worker uses persisted job state/leases, but a network request cannot be made exactly-once across a process crash. An uncertain request must not be blindly retried.

### 3.10 Findings & Evidence / triage

Findings are derived from persisted candidate execution reports: contract observation rows and failed explicit assertion rows. The user sees operation, candidate, execution status, details and triage controls. Triage is a separate record keyed to report plus evidence key. It does not edit the original execution evidence or make the program's classifier claim a defect.

### 3.11 Other destinations and prototype boundaries

Overview and history summarize project activity and persisted results. Collections and environments are project-owned resources. Some navigation destinations are generic/placeholder pages; see section 11. The frontend also contains legacy demo data for presentation components; demo-backed counters/cards are not evidence of live API behavior.

## 4. How the deterministic engines work

### 4.1 Parse and normalize

1. Accept JSON or YAML under the configured size limit.
2. Validate specification root, metadata, supported version, and `paths`.
3. For Swagger 2.0, map supported body/form/parameter/security/server structures into the OpenAPI 3 representation.
4. Enumerate supported HTTP operations.
5. Build a stable operation key from lowercase method, path, and operationId (or method/path fallback), then retain method, path, summary/description/tags, merged parameters, request body, and responses.
6. Resolve bounded local `$ref`s in the relevant normalized fragments; no outbound fetch is performed by parsing.

### 4.2 Deterministic candidate generation

The function `generate_candidates(operation, limit)` walks inline parameter schemas and inline JSON request-body schemas. It proposes:

| Candidate kind | Rule |
|---|---|
| `required-parameter-omitted` | Remove a required path/query/header parameter. |
| `parameter-enum-boundary` | Use a stable sentinel outside a declared enum. |
| `parameter-minimum-boundary` | For integer parameter with `minimum`, use one below it. |
| `parameter-length-boundary` | For bounded string `maxLength`, use one character too many, only within the safe generation cap. |
| `required-body-property-omitted` | Remove a required JSON body property. |
| `body-enum-boundary` | Use a deterministic value outside a body property's enum. |
| `body-minimum-boundary` | Use one below a numeric minimum. |
| `body-length-boundary` | Use a bounded string one character over `maxLength`. |
| `positive-baseline` | Keep user-supplied valid baseline unchanged as a control request. |

Candidate identity is a stable hash of operation scope, rule/reason, and mutation. There is no random generation. The implementation does not currently generate broad fuzz payloads, execute during preview, or cover every JSON Schema keyword. Candidate generation primarily understands inline schemas; limits and unsupported cases are detailed in section 11.

### 4.3 Contract-priority selection

Approach A generates the same candidate set and orders it by fixed categories: required-field omission first, enum boundaries next, then minimum/string-length boundaries, then remaining kinds; operation ID and candidate ID make ordering stable. It does not compute semantic scores. Candidate budget truncates the ordered list.

### 4.4 Semantic extraction and ranking

Approach B extracts facts from OpenAPI operation metadata and schema, including:

- operation intent inferred from HTTP method, operationId, path and descriptions;
- CRUD/resource relationships and possible create-before-lifecycle dependencies;
- required fields and parameters;
- field names, types, formats, descriptions and enums;
- constraints such as `minimum`, `maximum`, lengths and enum values;
- local schema references and source/evidence locations;
- possible constraint conflicts.

It attaches source operation/location, rule, evidence, and strength to facts. Each candidate then receives a score breakdown with four components: `contract_coverage`, `operation_intent`, `resource_workflow`, and `field_semantics`. The exact weights/rules live in `semantic.py`; total score is the sum. The engine sorts descending by score, then operation ID and candidate ID. The candidate budget selects a prefix of that order.

This is deterministic feature engineering, not learned prediction. The comparison demonstrates how semantic features alter candidate ranking/selection relative to a simple contract rule baseline. It does not prove Approach B finds more real defects for every API; that requires appropriate ground truth and repeated target runs.

### 4.5 Execution and response validation

Execution follows this sequence:

1. Validate supported method, explicit confirmation for non-read-only method, body byte limit, and header count.
2. Validate absolute HTTP(S) URL; reject embedded credentials and fragments.
3. Resolve host; check all resolved IPs; reject private/reserved destinations unless operator policy allows them. Loopback has a distinct local-development switch.
4. Pin the outgoing connection to one of the validated IPs while preserving original Host/SNI; disable environment proxies and automatic redirects.
5. Enforce connection/read/write/pool timeouts and a bounded response byte cap.
6. Parse JSON response when content type indicates JSON; return only allowlisted response headers.
7. Persist safe execution metadata. For candidate execution, evaluate explicit assertions and limited response-schema mismatches, then persist a redacted report without response body.

No automatic redirect following prevents redirects from escaping the validated destination. Redirect responses are returned as HTTP responses. DNS pinning reduces DNS rebinding exposure between validation and connection.

## 5. Vocabulary and flags

### Product/workflow terms

| Term | Meaning in this codebase |
|---|---|
| **Project** | Ownership/workspace scope for imported specs, saved requests, runs, reports, environments, and campaigns. |
| **Specification / contract** | Imported OpenAPI/Swagger document plus normalized operations. It describes expected behavior; it is not proof of deployed behavior. |
| **Operation** | One HTTP method + path entry in the parsed API contract. `operation_id` is the human/API operationId when available; `id` is IntelAPI's stable operation key used for joins and baselines. |
| **Candidate** | A proposed request variation with stable ID, kind, rationale and mutation. Preview status means not executed. |
| **Baseline** | User-supplied ordinary request values used to make an operation executable: path/query/header values and/or JSON body. Workbench derives required values from schema where possible. |
| **Positive baseline / positive case** | The unmutated expected-valid request/control candidate. “Positive” means valid-input control intent, not a guarantee that the target returns 2xx. |
| **Negative candidate / negative test** | A deliberate invalid or boundary mutation such as omitting required input or violating a declared enum/minimum. “Negative” describes the input relative to the contract, not that the test itself failed. |
| **Execution outcome** | Transport-level result such as `http_response`, `timeout`, `connection_error`, `blocked_by_policy`, or `response_too_large`. It answers whether/how the HTTP attempt completed. |
| **Assertion pass/fail** | Result of an explicit expected condition. A failed assertion is reviewable evidence, not automatically a defect. |
| **Contract observation** | A response status/content/schema behavior that differs from what the imported spec documents, or a bounded analysis result. An observation may be intentional, stale-contract behavior, or a real defect. |
| **Finding** | A review row derived from a contract observation or failed assertion in a persisted execution report. It is not necessarily a confirmed product defect. |
| **Triage** | Human decision attached to a finding observation plus optional note. Triage does not modify the underlying test or response. |
| **Generation report** | Persisted inventory of candidate suggestions; not evidence that tests ran. |
| **Execution report** | Persisted result/evidence from running one candidate. Response body is not persisted. |
| **Campaign** | Durable queued batch of test cases generated from a report and processed by the worker. |
| **Evidence / provenance** | The source and origin of an assertion/contract/fact. The semantic inspector carries rule, location, evidence and strength. |

### Finding triage choices

- **Untriaged** is the default when no human decision is saved.
- **Confirmed** means the reviewer accepts this observation as a defect. It is a human annotation, not a machine label.
- **False positive** means the reviewer believes the observation should not be treated as a defect in this context. It does not erase the response evidence.
- **Accepted risk** means the reviewer acknowledges the behavior/risk and chooses to accept it. It is distinct from false positive.

### POSITIVE / NEGATIVE, TP / FP / TN / FN

There are two different concepts that can sound alike:

1. `positive-baseline` is the normal valid-input candidate kind. Negative candidates are intentionally altered inputs. These are test design categories.
2. `true_positive`, `false_positive`, `true_negative`, and `false_negative` occur in the optional **seeded benchmark** ground-truth calculation. They compare an observed schema mismatch with a known seeded-defect case. They are benchmark labels, not general finding triage controls, not API HTTP status flags, and not reliable product-wide precision/recall truth.

The fixed local benchmark has one seeded case (`getWidget`, `widget_id=13`) where the response `id` is a string while the benchmark contract expects an integer. Its route is `/research-benchmark/widgets/{widget_id}`. The benchmark's TP/FP/TN/FN and seeded-detection metric code remains in the backend experiment response for benchmark runs, but the Workbench UI currently hides those removed metrics. They should not be interpreted for ordinary external APIs: absent benchmark ground truth means unknown/unavailable, not a negative result. For the one-defect fixture, the backend's false-negative accounting is intentionally simple and is not a general multi-defect evaluation framework.

### Boolean PASS/FAIL

`passed: true/false` on an assertion refers only to that assertion's configured expectation. `status_code=200` can pass while the response body is semantically wrong; a schema assertion can fail without proving customer impact. A transport/policy failure may have no HTTP status and is not a contract pass/fail.

## 6. What the metrics mean

Workbench metrics are principally about candidate generation/selection and the executions performed for that run:

| Metric family | Interpretation |
|---|---|
| Candidate counts / selection rate | How many deterministic suggestions were generated and what fraction were selected under the budget. |
| Operation coverage | Selected candidate operations divided by imported operations. This is selected test coverage, not runtime endpoint availability. |
| Constraint coverage | Selected supported minimum/maxLength/enum mutations divided by corresponding measurable constraints. It does not cover every schema constraint. |
| Generation/semantic extraction time | Local computation time for those phases, excluding network execution as defined by the API. Not a general throughput benchmark. |
| Executions/assertion counts/duration | Results for attempted selected candidates. A blocked request is not a target assertion failure. |
| Seeded detection / precision-style metrics | Benchmark-only ground-truth statistics. Hidden from the current Workbench presentation and not suitable as generic external-target quality metrics. |

Metrics can be `null` or shown as unavailable when the run has no relevant denominator, no execution, or no benchmark labels. They should not be replaced by zero: zero means a measured zero; unavailable means no valid calculation.

## 7. API and persistence sketch

The exact generated contract is available from FastAPI docs in development at `http://localhost:8000/docs`. Main route families (prefix `/api/v1`):

- `/projects`, `/projects/{project_id}`, project overview;
- `/specifications/parse`, `/discovery/scan`, project specification import/list/detail/readiness;
- project execution create/list and `/executions/ssrf-demo`;
- specification operation candidate preview, persisted generation reports and exports, candidate execution and execution report retrieval/export;
- project/specification `/experiments` create/list/detail/execute/compare/export;
- project saved requests, collections, environments;
- project health checks and runs;
- project findings and triage;
- project campaigns, cancellation, reports and events.

PostgreSQL stores projects, specifications, execution records, generation/execution reports, experiments, saved resources, health checks/assertion results, triage, campaign/test/job/event records. Alembic migrations under `apps/api/alembic/versions` describe schema evolution. The Compose file defines `db`, `api`, `worker`, and `web` services; PostgreSQL volume persists local state across container recreation unless the volume is explicitly removed.

## 8. Authentication and security model in this branch

This branch currently runs in a **local single-user development mode** using a local user record. It does not implement the planned Google sign-in/session flow; do not describe it as authenticated multi-user production software. The backend rejects applicable local-only project/execution workflows in production mode until auth is configured.

Environment interpolation supports project environment configuration. Secret handling is behind `core/secret_storage.py`; encryption requires a configured `ENVIRONMENT_ENCRYPTION_KEY`. Do not place real production credentials in the local demo.

Outbound target calls and remote spec discovery are security-sensitive. Respect the shared execution/discovery controls, network restrictions, size/time caps, and explicit state-changing request confirmation. `ALLOW_PRIVATE_NETWORK_TARGETS` is server-wide; it is not a per-project allowlist. Local targets are enabled by default in development for Docker/local testing.

## 9. Reproduction and demo setup

Use the root `README.md` and `docs/LOCAL_RUNBOOK.md` for full setup. For the already-built Compose application, the normal browser URL is `http://localhost:5173`; API readiness is `http://localhost:8000/health/ready`; interactive route schema docs are `http://localhost:8000/docs` in development.

For the real-response demo, use the public Swagger Petstore contract and only read-only `GET` calls. The safe SSRF panel is a preflight demonstration that sends no requests. Keep unsafe-method confirmation off for shared public APIs.

## 10. Determinism and reproducibility

Given the same normalized contract, candidate code/version, same budget, and same configuration, candidate IDs, mutations, fact extraction and ranking should repeat. Measured durations and live API responses naturally vary. A remote target can change independently of the saved spec; reports therefore reflect a contract snapshot and one execution-time observation, not a frozen target implementation.

Experiment records keep the specification hash and selection policy/version configuration. Generation and candidate execution reports are separately persisted. IDs are stable only within the documented deterministic identity construction; they are not universal semantic IDs across changed specs/rules.

## 11. Current limitations and how to talk about novelty honestly

- Semantic “understanding” is implemented as deterministic extraction from operation text, method/path signals, and inline/resolved contract schema facts. It is explainable and reproducible, but is not an LLM, embedding search, learned model, or broad natural-language reasoning system.
- Candidate rules cover selected required/enum/minimum/maxLength cases and a positive baseline. They are not exhaustive fuzzing, full OpenAPI conformance generation, authentication testing, stateful sequence synthesis, or property-based testing.
- Semantic workflow facts are inferred from static operation names/paths and relationships. They are hypotheses/heuristics, not proof that a real workflow dependency exists.
- The response-schema checker handles a bounded subset; composition and unresolved/complex schema paths can be reported as skipped. It is not a full JSON Schema validator.
- External API experiments can produce real responses, but semantic selection quality cannot be called accuracy without known ground truth. The local seeded fixture exists for controlled benchmark research only.
- The local seeded benchmark endpoint is part of this backend and can be used as an explicitly labeled local fixture; it must not be presented as a real public service.
- The SSRF panel compares active policy decisions against a textual simulation. It does not execute a vulnerable request or empirically measure a protected/unprotected attack pair.
- The backend has placeholder/legacy benchmark metrics beyond what the current Workbench displays. The removed seeded-detection, precision, recall, F1, detection-rate and time-to-first-defect metrics are not displayed in the current Workbench UI.
- The campaign worker is durable but does not provide exactly-once external request semantics. Shared public services can rate-limit or change data.
- Auth, multi-user tenancy, production deployment controls, broad telemetry, and full frontend end-to-end verification are outside the demonstrated local build.
- Some secondary destination cards/routes are generic or demo-backed. Treat persisted API operations/results as live; do not treat `apps/web/src/lib/demoData.ts` presentation content as project evidence.

**Novelty statement suitable for a presentation:** “IntelAPI explores a deterministic, explainable way to use semantic facts extracted from API contracts to prioritize boundary and negative test candidates against a contract-only baseline, while preserving provenance and routing live execution through a bounded SSRF-aware backend.” Avoid saying it automatically discovers confirmed vulnerabilities or that semantic ranking is proven superior on arbitrary APIs.

## 12. Suggested reading order for a new developer

1. `README.md` and `docs/LOCAL_RUNBOOK.md` — start and operate the stack.
2. `apps/web/src/app/router.tsx` and one page in `apps/web/src/features/` — trace the visible workflow.
3. `apps/api/app/api/router.py` and `apps/api/app/main.py` — find mounted backend routes.
4. `apps/api/app/modules/api_understanding/service.py` — parse/normalize/generate candidates.
5. `apps/api/app/modules/experiments/router.py` and `semantic.py` — experiment selection and ranking.
6. `apps/api/app/modules/execution/service.py` and `test_generation/router.py` — secure transport and result validation.
7. `apps/api/app/modules/campaigns/` — durable queued processing.
8. `apps/api/app/modules/findings/router.py`, `health_checks/router.py`, and `apps/api/app/models/` — user review and persistence.
9. `apps/api/tests/` — executable examples of intended boundary behavior. Tests show covered cases, not proof that every production concern is solved.

## 13. Change discipline

When changing behavior, update this as-built handoff plus relevant API/schema/runbook documentation. Add or update migrations for database shape changes. Keep all external target calls behind the approved security boundary. Keep machine observations separate from human triage. Preserve no-response-body persistence and redact secrets. Clearly label the local seeded fixture and any demo-only UI data.
