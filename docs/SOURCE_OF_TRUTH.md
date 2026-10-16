# IntelAPI — Product and Engineering Source of Truth

**Version:** 1.0
**Baseline date:** 2026-10-16
**Status:** Accepted baseline. Implementation remains incomplete; see `IMPLEMENTATION_STATUS.md`.

## 1. Product definition

IntelAPI is an AI-assisted API understanding, testing, execution, evidence, and adaptive test-campaign platform. It helps a developer move from an API contract or manually configured request to repeatable tests, observable executions, explainable findings, and a report that retains evidence.

The product is not an unrestricted vulnerability scanner, arbitrary Internet proxy, or LLM wrapper. The system must execute only within explicit security policy and must distinguish facts from hypotheses.

### 1.1 User needs

A user needs to:

1. Configure and send an API request without needing an LLM key.
2. inspect status, latency, headers, and a bounded response body.
3. save requests, collections, and environment configuration inside a project.
4. import an OpenAPI document from a file or URL and inspect normalized operations.
5. run repeatable health checks with explicit assertions.
6. generate positive, negative, boundary, schema-oriented, and workflow-oriented test candidates.
7. preview candidates before creating a campaign, without persisting the preview.
8. execute candidates through one secure outbound-request boundary.
9. understand why an execution passed, failed, or produced a potential finding.
10. trace each finding to executions and evidence with provenance.
11. run durable campaigns that survive API/worker restarts, inspect progress/events, cancel, and retrieve partial or final reports.
12. review a project overview with aggregate activity and outcome metrics.

### 1.2 Product principles

- **Contract-first, evidence-backed:** contracts, extracted facts, observed behavior, and inferred hypotheses remain distinguishable.
- **Deterministic baseline:** core request execution, candidate generation, assertions, and classification must work without LLM credentials.
- **LLM optional:** providers are adapters behind an internal interface; provider-specific behavior must not leak into domain modules.
- **No automatic defect claims:** an unexpected response is an observation. A finding requires explicit evidence and classification rules.
- **One execution boundary:** every outbound target request, including URL-based specification import, passes through security controls appropriate to that operation.
- **Durable state:** projects, executions, campaigns, jobs, events, findings, and evidence references persist in PostgreSQL.
- **Reproducibility:** store immutable, redacted execution snapshots and version references needed to explain what was tested.
- **Least privilege:** all saved resources belong to a project, and the server enforces ownership on every read, write, and execution.
- **Bounded retention:** bodies, specification documents, excerpts, time, executions, and campaign iterations have explicit limits.
- **Modular monolith:** one API application and one separate campaign worker process; no microservices or infrastructure expansion without an approved decision.

## 2. Scope

### 2.1 MVP product destinations

1. **Overview** — project-level activity and outcome aggregates.
2. **API Workspace** — request editor, execution, response viewer, collections, environments, and history.
3. **Health Checks** — saved checks, fixed assertions, runs, and history.
4. **API Explorer** — OpenAPI import, normalized operations, and non-persisting candidate preview.
5. **Test Campaigns** — campaign creation, durable execution, progress, cancellation, event timeline, tests, executions, and report.
6. **Findings & Evidence** — classified findings, user-managed triage fields, evidence provenance, and traceability.

Supporting capabilities include Google sign-in/session, projects/archive, collections, saved requests, environments, request history, specification import, and report retrieval.

### 2.2 Explicit non-goals for MVP

- Microservices, Kubernetes, Redis, Celery, vector databases, graph databases, or a custom ML training pipeline.
- Requiring an LLM to use the ordinary workspace or deterministic test path.
- Claiming that every unexpected status or schema difference is a defect.
- Direct frontend-to-database access.
- Blindly retrying target requests whose send/response outcome is uncertain after a process crash.
- Permanent project deletion in the MVP.
- Unbounded request/response/specification storage or execution budgets.

## 3. Roles, authorization, and tenancy

### 3.1 Product roles

The MVP has a signed-in application user. No separate admin, organization, or project-role hierarchy is currently approved. Do not invent role types in the schema without a decision.

- A user may access only projects they own.
- All collections, requests, environments, specifications, operations, health checks, executions, tests, campaigns, findings, evidence, and reports are project-scoped directly or through a parent resource.
- The server verifies ownership for reads, mutations, imports, and outbound execution. Frontend route guards are not authorization.
- Archive is a soft-delete operation. Archived projects cannot accept new normal work unless a later approved rule explicitly permits it; historical data remains available according to retention policy.
- A user cannot read another user's resources by changing a UUID in a URL.

### 3.2 Authentication/session rules

- Verify Google ID tokens on the backend. Use Google's stable `sub` as identity key; email is an attribute, not the primary identity key.
- The browser sends an opaque random application session token in an `HttpOnly` cookie.
- Persist only a cryptographic hash of the session token. Store expiry and revocation state.
- Cookie `Secure` is mandatory in production. Set `SameSite` to match the deployment topology; validate allowed origins and enforce CSRF protection for state-changing cookie-authenticated requests.
- Google client configuration may be public; provider secrets, session-signing/encryption keys, and environment secrets remain server-side.
- Logout revokes the session server-side and expires the cookie.
- Never log ID tokens, session tokens, OAuth secrets, environment secrets, authorization headers, or unredacted sensitive bodies.

## 4. System architecture

### 4.1 Runtime topology

```text
Browser (React/Vite/TypeScript)
          |
          | same-origin / configured API base; session cookie
          v
FastAPI application (/api/v1)
  |-- Auth + ownership checks
  |-- Product/domain routers and services
  |-- Shared secure outbound execution service
  |-- PostgreSQL persistence via SQLAlchemy
  |-- Campaign/job transaction and event creation
          |
          +----------------------> PostgreSQL
          |                           ^
          | durable jobs + leases     | claim/complete/event
          v                           |
Separate campaign worker -------------+
          |
          v
Target API (only through outbound security policy)
```

The campaign worker is a separate process from the API, but both are part of one modular monolith and share domain services and database contracts. The worker is not an excuse to duplicate execution logic.

### 4.2 Technology baseline

- Web: React, Vite, TypeScript.
- API: Python, FastAPI, Pydantic.
- Persistence: PostgreSQL, SQLAlchemy 2.x, Alembic.
- HTTP client: HTTPX behind the shared execution boundary.
- Tests: pytest; frontend tests and E2E coverage are required as features are added.
- Local orchestration: Docker Compose.
- CI: lint, typecheck, unit/integration tests, migration checks, generated API type drift checks, and build.

Do not replace the established stack or add infrastructure without a recorded decision approved by Developer A and the teammate.

### 4.3 Layering rules

- **Router:** HTTP parsing, authentication/authorization dependency use, status codes, response schemas. Keep business logic out.
- **Schema/DTO:** request and response validation. Do not use ORM objects as public DTOs.
- **Service:** use-case orchestration and transaction boundaries.
- **Repository:** persistence queries; every query must preserve project ownership.
- **Domain module:** domain logic with no HTTP framework dependency where practical.
- **Integration adapter:** external provider or transport implementation behind a stable interface.
- **Worker:** claim durable jobs, acquire/renew/release leases, invoke shared orchestration, persist state/events. It must not implement a second HTTP transport.
- **Migration:** every schema change uses Alembic. Never use `Base.metadata.create_all()` as a production or test migration substitute.

## 5. Cross-cutting HTTP contract

### 5.1 Routes and identifiers

- Product API prefix: `/api/v1`.
- Health probes stay outside the versioned prefix: `GET /health/live`, `GET /health/ready`.
- Resource IDs use UUIDs.
- FastAPI's generated OpenAPI schema is authoritative for HTTP request/response types.
- Generate TypeScript API types in CI to `apps/web/src/services/generated/api-schema.ts`; generated output is not hand-edited.

### 5.2 Errors

Use one structured error envelope:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request is invalid.",
    "details": {}
  }
}
```

`details` is optional and must not leak secrets or internals. Stable codes include:

| HTTP | Code | Meaning |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing/invalid/expired session |
| 403 | `FORBIDDEN` | Authenticated but not authorized |
| 403 | `TARGET_BLOCKED` | Outbound target rejected by policy |
| 404 | `NOT_FOUND` | Missing resource or resource hidden by ownership policy |
| 409 | `CONFLICT` | State or uniqueness conflict |
| 422 | `VALIDATION_ERROR` | Invalid input |
| 504 | `TARGET_TIMEOUT` | Target execution timed out |
| 500 | `INTERNAL_ERROR` | Unexpected internal error; no stack trace in public response |

### 5.3 Pagination

List endpoints accept `limit` (default 50, maximum 100) and `offset` (default 0). Return:

```json
{
  "items": [],
  "pagination": {"limit": 50, "offset": 0, "total": 0}
}
```

Validate negative/oversized values. `total` must reflect the same authorization and filter scope as `items`.

## 6. Product features mapped to technical modules

### 6.1 Identity and projects

**User-visible behavior:** Google sign-in, current-user lookup, logout, create/list/get/update/archive projects, project overview.

**Modules:** `auth`, `projects`, `overview`, `core/security.py`, session models, project ownership dependencies.

**Core invariants:** Google `sub` identity; hashed revocable sessions; project ownership checked server-side; archive is soft delete; no permanent delete endpoint in MVP.

### 6.2 API Workspace

**User-visible behavior:** edit/send HTTP requests, inspect bounded response, save requests and collections, resolve environment variables, inspect request history and execution detail.

**Modules:** `workspace/requests`, `workspace/collections`, `workspace/environments`, `execution`, `history`.

**Core invariants:** all requests go through shared outbound policy; resolved request snapshot is immutable and redacted; environment secrets are encrypted at rest and never returned in plaintext after write; non-2xx is still an HTTP response, not a transport error.

### 6.3 API understanding / Explorer

**User-visible behavior:** import OpenAPI from file or URL, view specification and normalized operations, inspect operation details, preview candidate tests.

**Modules:** `api_understanding`, `knowledge`, `test_generation`, `integrations/llm`.

**Core invariants:** URL import uses the safe fetch boundary with DNS/redirect revalidation, strict time/size limits, and content validation. The OpenAPI parser must not perform its own network fetches. Original JSON spec is bounded, stored as JSONB with hash/version metadata. Candidate preview does not persist candidates.

### 6.4 Health Checks

**User-visible behavior:** define checks, run them, review run history and assertion outcomes.

**Modules:** `health_checks`, shared `execution`, `analysis/assertions.py`, `evidence`.

**Fixed MVP assertion types:**
1. HTTP status code.
2. Latency threshold.
3. JSON path/value.
4. Response header.
5. Response schema.

Assertions are deterministic and explicit. A failed assertion is evidence of a mismatch, not automatically a confirmed defect.

### 6.5 Test generation and intelligence

**User-visible behavior:** produce candidate tests for positive, negative, boundary, schema, and workflow behavior; optionally use an LLM to enrich candidate generation.

**Modules:** `test_generation/deterministic.py`, `validation.py`, `deduplication.py`, `llm_assisted.py`, `integrations/llm`, `api_understanding`, `knowledge`.

**Core invariants:** deterministic candidate baseline exists without LLM credentials; candidate inputs and provenance are traceable; generated tests are validated and deduplicated before use; no arbitrary unbounded payloads.

### 6.6 Execution and analysis

**User-visible behavior:** execute requests/candidates, evaluate assertions, classify potential findings, preserve evidence.

**Modules:** `execution`, `analysis`, `evidence`, `findings`.

**Core invariants:** one outbound transport service; request/response/time budgets; response caps; redaction; non-2xx is not automatically transport failure; findings have evidence and provenance; facts carry provenance `DECLARED`, `EXTRACTED`, `OBSERVED`, or `INFERRED`.

### 6.7 Adaptive campaigns

**User-visible behavior:** create a campaign from a specification/operation or selected inputs; track tests/executions/events; cancel; inspect report including partial report after failure/cancellation if evidence exists.

**Modules:** `campaigns`, `adaptive`, `test_generation`, `execution`, `analysis`, `evidence`, `reports`.

**Core invariants:** campaign states are `queued`, `running`, `completed`, `failed`, `cancelled`; terminal states cannot reopen. Campaign creation atomically persists campaign, durable job, and initial event before returning `202 Accepted`. Worker claims use PostgreSQL row locks and leases with recovery. Retry only failures known to have occurred before a request was sent. Do not promise exactly-once target execution. Uncertain post-crash outcomes are recorded and not blindly repeated. Budget exhaustion ends in `completed` with a `budget_exhausted` event. Cancellation of a terminal campaign is idempotent and returns the unchanged state (`200`).

### 6.8 Findings, evidence, and reports

**User-visible behavior:** list findings, inspect details/evidence, update user-managed triage fields, retrieve campaign report.

**Modules:** `findings`, `evidence`, `reports`, `overview`.

**Core invariants:** evidence links to its source execution/assertion/specification/knowledge fact; bounded redacted excerpts; no duplicated authoritative counters at first; derive counts from tests/executions until measured performance justifies denormalization. Finding PATCH may change only user-managed fields such as status/severity; machine-derived classification must not be overwritten by arbitrary client fields.

## 7. Data and persistence decisions

The following decisions are accepted and are normative:

| ID | Decision |
|---|---|
| DB-01 | Projects use `deleted_at` soft deletion; no permanent-delete endpoint in MVP. Preserve historical records. |
| DB-02 | Environment secrets are encrypted with a server-side configuration key. Never return plaintext after write; redact in logs, errors, snapshots, and evidence. |
| DB-03 | Store bounded original JSON OpenAPI spec in JSONB with content hash/version metadata; reject oversized documents. |
| DB-04 | Store immutable execution snapshot of resolved method, URL, safe headers, redacted body, and relevant environment/spec version references. |
| DB-05 | Store bounded response excerpts/metadata with configurable retention; do not promise indefinite raw body retention. |
| DB-06 | `campaign_events` is append-only. Do not add a separate finding-status history table in the initial schema. |
| DB-07 | Derive campaign/report counts from tests/executions initially; avoid duplicated authoritative counters. |
| DB-08 | Claim jobs transactionally with row locks and lease expiry/recovery. |
| DB-09 | Retry only failures known to precede sending a request. An uncertain after-crash outcome is recorded, not blindly retried. |
| DB-10 | Evidence has source relationship and provenance `DECLARED`, `EXTRACTED`, `OBSERVED`, or `INFERRED`, plus bounded redacted excerpts. |

### 7.1 Planned core tables

`users`, `sessions`, `projects`, `collections`, `saved_requests`, `environments`, `environment_variables`, `executions`, `assertion_results`, `api_specifications`, `api_operations`, `knowledge_facts`, `health_checks`, `test_cases`, `campaigns`, `campaign_jobs`, `findings`, `evidence_references`, `campaign_events`.

All schema changes are Alembic migrations. Proposed migration groups are `0002_identity_projects.py`, `0003_workspace_assets.py`, `0004_execution_api_understanding.py`, `0005_testing_campaigns.py`, and `0006_findings_evidence.py`. These names are proposals, not a license to rewrite ancestry: inspect the current revision graph before creating revisions.

## 8. Canonical API inventory

All routes below are under `/api/v1` unless shown otherwise. This is the accepted target inventory, not a claim that all routes exist.

### Auth
- `GET /auth/google/config`
- `POST /auth/google/session`
- `GET /auth/me`
- `POST /auth/logout`

### Projects and overview
- `GET /projects`
- `POST /projects`
- `GET /projects/{project_id}`
- `PATCH /projects/{project_id}`
- `POST /projects/{project_id}/archive`
- `GET /projects/{project_id}/overview`

### Collections and saved requests
- `GET/POST /projects/{project_id}/collections`
- `GET/PATCH/DELETE /collections/{collection_id}`
- `GET/POST /projects/{project_id}/requests`
- `GET/PATCH/DELETE /requests/{request_id}`
- `POST /requests/execute`
- `GET /projects/{project_id}/history`
- `GET /executions/{execution_id}`

### Environments
- `GET/POST /projects/{project_id}/environments`
- `GET/PATCH/DELETE /environments/{environment_id}`

### Specifications and operations
- `GET /projects/{project_id}/specifications`
- `POST /projects/{project_id}/specifications/import` (file upload or URL import)
- `GET /specifications/{specification_id}`
- `GET /specifications/{specification_id}/operations`
- `GET /operations/{operation_id}`
- `POST /operations/{operation_id}/candidates/preview` (non-persisting)

### Health checks
- `GET/POST /projects/{project_id}/health-checks`
- `GET/PATCH/DELETE /health-checks/{check_id}`
- `POST /health-checks/{check_id}/run`
- `GET /health-checks/{check_id}/runs`

### Campaigns
- `GET/POST /projects/{project_id}/campaigns`
- `GET /campaigns/{campaign_id}`
- `POST /campaigns/{campaign_id}/cancel`
- `GET /campaigns/{campaign_id}/tests`
- `GET /campaigns/{campaign_id}/executions`
- `GET /campaigns/{campaign_id}/events`
- `GET /campaigns/{campaign_id}/report`

### Findings and evidence
- `GET /projects/{project_id}/findings`
- `GET/PATCH /findings/{finding_id}`
- `GET /findings/{finding_id}/evidence`
- `GET /evidence/{evidence_id}`

## 9. Shared DTO contracts

The following shared concepts must be agreed before independent implementation. API response schemas and domain models remain separate.

- `UserRead`
- `ProjectCreate`, `ProjectRead`
- `RequestDefinition`
- `ExecutionResult`: `id`, outcome (`http_response`, `timeout`, `connection_error`, `blocked_by_policy`, `response_too_large`, `execution_error`), optional `status_code`, `duration_ms`, response headers, bounded body, transport error, start/completion timestamps. A non-2xx status is still `http_response`.
- `NormalizedOperation`
- `TestCandidate`
- `AssertionResult`
- `FindingRead`
- `EvidenceReferenceRead`
- `CampaignCreate`, `CampaignRead`, `CampaignReport`

## 10. Security requirements

### 10.1 Outbound request security

One shared policy/transport boundary is mandatory for ordinary execution, health checks, campaign runs, and URL-based specification import. It must:

- allow only supported URL schemes (HTTP/HTTPS);
- reject loopback, private, link-local, multicast, reserved, and otherwise disallowed IP ranges by default;
- resolve DNS and validate all resolved addresses before connecting;
- revalidate redirects and block redirect-based policy bypass;
- defend against DNS rebinding by binding validation to the actual connection strategy;
- enforce connect/read/total timeouts, request/response size caps, redirect limits, concurrency limits, and campaign budgets;
- avoid forwarding browser cookies, internal credentials, cloud metadata credentials, or arbitrary internal headers;
- redact authorization headers, cookies, configured secret values, and sensitive body fields from snapshots/logs/evidence;
- return a stable `TARGET_BLOCKED` or `TARGET_TIMEOUT` error without leaking network internals.

If an implementation cannot guarantee DNS/connection validation, it must fail closed. URL-import parsing must never silently fetch remote references.

### 10.2 Retention and observability

- Bound request/response bodies, OpenAPI documents, excerpts, and log fields.
- Use configurable retention and document the local defaults in environment examples.
- Do not store plaintext environment secrets in API response DTOs, logs, test snapshots, or evidence.
- Use structured logs with request/correlation IDs and safe error metadata.
- Never log stack traces or internal exception text in public error responses.

## 11. Testing and quality gates

Required layers:

1. **Unit tests:** domain logic, parsers, candidate validation/deduplication, assertions, state machine, adaptive scoring.
2. **PostgreSQL integration tests:** migrations from empty DB, ownership isolation, uniqueness/transactions, durable campaign/job recovery, persistence across restart.
3. **Outbound security tests:** private IPs, DNS resolution, redirects, DNS rebinding assumptions, timeouts, oversize responses, header/body redaction.
4. **Frontend tests:** API client errors, auth/session state, candidate preview, campaign states, finding evidence rendering.
5. **E2E:** auth/project lifecycle; request execution/history; OpenAPI import/preview; campaign → executions → findings/evidence → report.
6. **CI checks:** backend lint/tests, frontend lint/typecheck/tests/build, PostgreSQL migration/integration test, generated OpenAPI TypeScript drift check.

A passing scaffold test suite is not proof of feature completeness.

## 12. Accepted decisions register

The accepted cross-cutting decisions C-01 through C-14 are represented in this document: route prefix; common errors; pagination; Google `sub`; hashed opaque sessions; project ownership; SQLAlchemy/Alembic layering; shared secure outbound execution; deterministic baseline/optional LLM; evidence traceability; durable campaign queue; no exactly-once claim; soft delete/retention; testing layers.

Additional accepted decisions:
- fixed five health assertion types;
- terminal campaign cancellation is idempotent;
- candidate preview is non-persisting;
- specification import supports file and URL with safe URL fetch;
- dedicated project overview endpoint;
- CI-generated TypeScript types at `apps/web/src/services/generated/api-schema.ts`.

### 12.1 Liveness compatibility

The last verified implementation returns `{"status":"alive"}` from `/health/live`, while an older proposed contract example used `{"status":"ok"}`. The canonical contract preserves the implemented `"alive"` response until a reviewed compatibility change is approved. Do not silently change the response in an unrelated feature PR.

## 13. Change control

A product, security, API, database, module-boundary, or ownership change requires:
1. a written decision in this file;
2. affected plan/status/runbook updates;
3. a review from Developer A and Developer B;
4. migration and compatibility analysis where applicable;
5. tests that enforce the new invariant.

When this file and implementation disagree, record the discrepancy and make a planned change. Do not infer that code is correct merely because it exists.
