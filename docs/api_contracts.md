# IntelAPI — API Contracts

**Version:** 1.0
**Baseline date:** 2026-10-16
**Status:** Frozen target contract for implementation; not a claim that every route already exists.
**Authority:** `SOURCE_OF_TRUTH.md` governs product rules and cross-cutting decisions. `DATABASE_SCHEMA.md` governs persistence. If implementation differs, raise a contract-change PR rather than silently changing this file.

## 1. Contract rules

### 1.1 Base paths and content types

- Product API prefix: `/api/v1`.
- Health probes are intentionally outside the versioned prefix: `GET /health/live` and `GET /health/ready`.
- JSON request/response bodies use `application/json`, except specification file import, which uses `multipart/form-data`.
- All timestamps are ISO 8601 UTC strings.
- Resource IDs are opaque UUIDs. Clients must not infer ownership or authorization from an ID.
- JSON fields use `snake_case` on the wire.
- Unknown request fields should be rejected where practical for write DTOs; response DTOs must not expose secrets or internal ORM fields.
- The FastAPI-generated OpenAPI document is authoritative for the machine-readable HTTP schema. The generated TypeScript contract at `apps/web/src/services/generated/api-schema.ts` must be refreshed from it; do not hand-edit the generated file.

### 1.2 Authentication and authorization

- All `/api/v1` routes require a valid application session except `GET /api/v1/auth/google/config` and `POST /api/v1/auth/google/session`.
- Google ID tokens are verified by the backend. The stable Google `sub` is the identity key; email is not an identity key.
- The backend issues an opaque, cryptographically random application session token. Only a hash is persisted.
- The session is transported in an `HttpOnly` cookie. Set `Secure` in production; configure `SameSite` according to deployment topology and validate the allowed `Origin`/CSRF token for state-changing requests.
- Every project-owned resource must be checked against the authenticated user's project ownership on every read, write, import, and execution. A client-side route guard is not authorization.
- Cross-owner resources should generally return `404 NOT_FOUND` to avoid disclosing their existence. Use `403 FORBIDDEN` for an authenticated user who is explicitly disallowed from an otherwise visible action.
- Never return environment secret plaintext after it has been written. Never log session tokens, Google ID tokens, secret values, authorization headers, or unredacted sensitive request/response content.

### 1.3 Standard error envelope

All application errors use this shape:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request is invalid.",
    "details": [{ "field": "name", "issue": "Field is required." }]
  }
}
```

`details` is optional and may be an object or a list of field issues. Clients must branch on stable `code`, not on message text.

| HTTP | Code | Meaning |
|---:|---|---|
| 400 | `BAD_REQUEST` | Request cannot be interpreted. |
| 401 | `UNAUTHENTICATED` | Missing, expired, or invalid session. |
| 403 | `FORBIDDEN` | Authenticated user lacks permission. |
| 403 | `TARGET_BLOCKED` | Outbound target rejected by security policy. |
| 404 | `NOT_FOUND` | Resource absent or intentionally hidden due to ownership. |
| 409 | `CONFLICT` | State transition or uniqueness conflict. |
| 413 | `PAYLOAD_TOO_LARGE` | Request, response, or specification exceeds configured limit. |
| 422 | `VALIDATION_ERROR` | DTO or domain validation failed. |
| 429 | `RATE_LIMITED` | Request or execution budget/rate limit exceeded. |
| 502 | `TARGET_CONNECTION_ERROR` | Target connection failed before a usable HTTP response. |
| 504 | `TARGET_TIMEOUT` | Target operation timed out. |
| 500 | `INTERNAL_ERROR` | Unexpected server-side failure; do not expose stack traces. |

An outbound execution endpoint may return HTTP `200` with an `ExecutionResult` whose `outcome` is `timeout`, `connection_error`, or `blocked_by_policy` when the execution itself was successfully recorded. Request-level validation/auth/policy failures that prevent creating an execution use the standard HTTP error envelope. The implementation must apply this distinction consistently.

### 1.4 Pagination and ordering

List endpoints support:

- `limit`: default `50`, minimum `1`, maximum `100`.
- `offset`: default `0`, minimum `0`.
- Default ordering: newest first by `created_at`, unless a resource-specific ordering is stated.

List response shape:

```json
{
  "items": [],
  "pagination": { "limit": 50, "offset": 0, "total": 0 }
}
```

`total` is the count matching the filters before pagination. Do not return unbounded lists.

### 1.5 Common data rules

- IDs are UUID strings; timestamps are ISO 8601 UTC.
- Durations use integer milliseconds (`duration_ms`).
- Secrets are write-only. Responses may include `has_value: true|false`, never plaintext.
- Response bodies, request snapshots, imported specifications, evidence excerpts, and logs are bounded and redacted according to configuration.
- An HTTP non-2xx response is still an HTTP response, not a transport error.
- Unexpected behavior is evidence/observation, not automatically a defect.

## 2. Shared DTOs

The schemas below define semantic fields. Pydantic models and generated OpenAPI may add precise field constraints, enum definitions, and nullable annotations, but must not contradict these contracts.

### 2.1 User and project

```json
{
  "UserRead": {
    "id": "uuid",
    "email": "user@example.com",
    "display_name": "User",
    "avatar_url": null,
    "created_at": "2026-10-16T08:00:00Z"
  },
  "ProjectCreate": { "name": "Payments API", "description": "Optional description" },
  "ProjectRead": {
    "id": "uuid", "name": "Payments API", "description": "Optional description",
    "created_at": "2026-10-16T08:00:00Z", "updated_at": "2026-10-16T08:00:00Z",
    "archived_at": null
  }
}
```

### 2.2 Request definition and execution result

```json
{
  "RequestDefinition": {
    "project_id": "uuid",
    "name": "Get account",
    "method": "GET",
    "url": "https://api.example.com/accounts/123",
    "headers": { "Accept": "application/json" },
    "query_params": {},
    "body": null,
    "body_type": "none",
    "environment_id": null
  },
  "ExecutionResult": {
    "id": "uuid",
    "outcome": "http_response",
    "status_code": 200,
    "duration_ms": 84,
    "response_headers": { "content-type": "application/json" },
    "body": { "excerpt": "{\"id\":123}", "truncated": false, "content_type": "application/json" },
    "transport_error": null,
    "started_at": "2026-10-16T08:00:00Z",
    "completed_at": "2026-10-16T08:00:00Z"
  }
}
```

`ExecutionResult.outcome` enum:
- `http_response`
- `timeout`
- `connection_error`
- `blocked_by_policy`
- `response_too_large`
- `execution_error`

`status_code` is nullable and is populated only when an HTTP response was received. The stored execution snapshot contains the resolved method, URL, safe headers, redacted body, and relevant environment/specification version references. Secrets must not be copied into a snapshot in plaintext.

### 2.3 API understanding and candidate DTOs

`NormalizedOperation` includes `id`, `specification_id`, `operation_key`, `method`, `path`, `summary`, `parameters`, `request_body_schema`, `response_schemas`, `security_requirements`, and timestamps as applicable. Operation schemas are normalized representations; they do not assert that the target behaves as declared.

`TestCandidate` includes `id` (preview candidates may use a transient identifier), `operation_id`, `category`, `name`, `description`, `request_template`, `expected_assertions`, `rationale`, `source_refs`, and `confidence`. Candidate categories are `positive`, `negative`, `boundary`, `schema`, and `workflow`. Preview results are not persisted; campaign creation persists the candidates it accepts.

### 2.4 Assertions, findings, evidence

- `AssertionResult`: `id`, `execution_id`, `assertion_type`, `passed`, `expected`, `actual`, `message`, `created_at`.
- `FindingRead`: `id`, `project_id`, `campaign_id`, `test_case_id`, `execution_id`, `title`, `description`, `classification`, `severity`, `status`, `confidence`, `created_at`, `updated_at`.
- `EvidenceReferenceRead`: `id`, `finding_id`, `execution_id`, `source_type`, `provenance`, `summary`, `excerpt`, `created_at`.
- `provenance` is one of `DECLARED`, `EXTRACTED`, `OBSERVED`, `INFERRED`.
- Finding `status` and `severity` are user-managed triage fields where exposed. Classification and evidence links are system-derived and must not be silently overwritten by a triage update.

### 2.5 Campaign DTOs

`CampaignCreate` contains `project_id`, `name`, `specification_id` or an explicit operation selection, generation options, and finite budgets (`max_executions`, `max_iterations`, `max_elapsed_seconds`). The API must reject missing/invalid scope and non-positive or above-policy budgets.

`CampaignRead` contains `id`, `project_id`, `name`, `state`, `created_at`, `started_at`, `completed_at`, `cancel_requested_at`, and a bounded progress summary. States: `queued`, `running`, `completed`, `failed`, `cancelled`.

`CampaignReport` contains campaign metadata, aggregate counts derived from test cases/executions, findings summary, execution outcomes, budget/termination reason, and links/IDs to evidence. Do not maintain duplicated authoritative counters unless a later decision explicitly approves them.

## 3. Endpoint inventory

All paths below are relative to `/api/v1`. Unless listed as public, endpoints require a valid application session and project ownership checks. Query pagination parameters apply to list endpoints.

### 3.1 Authentication

| Method and path | Request | Success |
|---|---|---|
| `GET /auth/google/config` | None | `200 { "client_id": "..." }` (public, no secret) |
| `POST /auth/google/session` | `{ "id_token": "..." }` | `200 UserRead`; sets application session cookie |
| `GET /auth/me` | None | `200 UserRead` |
| `POST /auth/logout` | None | `204`; revokes current session and clears cookie |

Authentication requirements:
- Verify issuer, audience, signature, expiry, and relevant claims of Google's ID token on the backend.
- Do not accept a client-supplied email as proof of identity.
- Session token is opaque/random; store only its cryptographic hash, expiry, revocation state, and user reference.
- Login/session creation and logout must have abuse controls and security-relevant logging without logging credentials.
- State-changing cookie-authenticated routes validate allowed origin and CSRF defense.

### 3.2 Projects and overview

| Method and path | Request | Success |
|---|---|---|
| `GET /projects` | Pagination; excludes archived by default unless `include_archived=true` is supported explicitly | `200 List[ProjectRead]` envelope |
| `POST /projects` | `ProjectCreate` | `201 ProjectRead` |
| `GET /projects/{project_id}` | None | `200 ProjectRead` |
| `PATCH /projects/{project_id}` | Partial `name`, `description` | `200 ProjectRead` |
| `POST /projects/{project_id}/archive` | Optional `{ "archived": true }`; default archives | `200 ProjectRead` |
| `GET /projects/{project_id}/overview` | None | `200 OverviewRead` aggregate |

Archive is soft deletion (`archived_at`/equivalent). MVP does not expose permanent project deletion. Archived projects retain history; new normal work is rejected unless explicitly allowed by a later accepted decision. `OverviewRead` returns bounded aggregate metrics and recent activity derived from persisted resources, not a frontend-computed mock.

### 3.3 Collections

| Method and path | Request | Success |
|---|---|---|
| `GET /projects/{project_id}/collections` | Pagination | `200 List[CollectionRead]` |
| `POST /projects/{project_id}/collections` | `{ "name": "Regression", "description": null }` | `201 CollectionRead` |
| `PUT /projects/{project_id}/collections/{collection_id}` | `{ "name": "Regression", "description": null }` | `200 CollectionRead` |
| `DELETE /projects/{project_id}/collections/{collection_id}` | None | `204` |

Collection deletion must follow the accepted FK policy and must not cascade-delete execution history. A collection may organize saved requests; requests and executions retain their own project association.

### 3.4 Saved requests, execution, and history

| Method and path | Request | Success |
|---|---|---|
| `GET /projects/{project_id}/requests` | Pagination; optional collection filter | `200 List[SavedRequestRead]` |
| `POST /projects/{project_id}/requests` | `RequestDefinition` without `project_id` duplication if path is authoritative | `201 SavedRequestRead` |
| `GET /requests/{request_id}` | None | `200 SavedRequestRead` |
| `PATCH /requests/{request_id}` | Partial editable request fields | `200 SavedRequestRead` |
| `DELETE /requests/{request_id}` | None | `204` |
| `POST /requests/execute` | `{ "request": RequestDefinition, "save_to_history": true }` or saved request reference plus explicit overrides | `200 ExecutionResult` |
| `GET /projects/{project_id}/history` | Pagination; optional method/status/outcome/date filters | `200 List[ExecutionSummary]` |
| `GET /executions/{execution_id}` | None | `200 ExecutionResult` with redacted snapshot metadata |

Execution contract:
- All target requests go through the single shared outbound execution service.
- Enforce scheme, host, DNS, resolved-IP, redirect, timeout, request-size, response-size, header, and execution-budget controls. Block loopback, private, link-local, and other prohibited destinations by default.
- Revalidate DNS and destination policy on redirects and immediately before connecting to mitigate rebinding. Never allow the HTTP client to follow redirects without policy validation.
- Non-2xx target responses are returned as `outcome: "http_response"` with their status code.
- Capture bounded response excerpts and selected safe headers; redact credentials and sensitive values.
- Persist the immutable redacted execution snapshot and execution result when history is enabled. Campaign execution always persists the required execution record.
- `POST /requests/execute` does not permit bypassing target policy through headers, environment variables, redirect behavior, or an alternate client.

### 3.5 Environments and environment variables

| Method and path | Request | Success |
|---|---|---|
| `GET /projects/{project_id}/environments` | Pagination | `200 List[EnvironmentRead]` |
| `POST /projects/{project_id}/environments` | `{ "name": "Staging", "base_url": "https://staging.example.com" }` | `201 EnvironmentRead` |
| `GET /environments/{environment_id}` | None | `200 EnvironmentRead` (no secret plaintext) |
| `PATCH /environments/{environment_id}` | Partial non-secret fields | `200 EnvironmentRead` |
| `DELETE /environments/{environment_id}` | None | `204` |
| `PUT /environments/{environment_id}/variables/{key}` | `{ "value": "...", "is_secret": true }` | `200 EnvironmentVariableRead` with `has_value`, never value |
| `DELETE /environments/{environment_id}/variables/{key}` | None | `204` |

Environment variable endpoints are part of the frozen contract even if not yet implemented. Encrypt secret values at rest with a server-side configuration key; do not use a key stored alongside the ciphertext in the database. A secret write response must not echo the submitted value. Resolver substitution must be bounded and must not allow variable expansion to bypass outbound URL policy. Secret values must be redacted from logs, execution snapshots, errors, and evidence.

### 3.6 OpenAPI specifications and operations

| Method and path | Request | Success |
|---|---|---|
| `GET /projects/{project_id}/specifications` | Pagination | `200 List[SpecificationRead]` |
| `POST /projects/{project_id}/specifications/import` | `multipart/form-data` file upload **or** JSON `{ "url": "https://.../openapi.json", "name": "Optional name" }` | `201 SpecificationRead` |
| `GET /specifications/{specification_id}` | None | `200 SpecificationRead` metadata; raw document only if explicitly requested by contract |
| `GET /specifications/{specification_id}/operations` | Pagination; optional method/tag filters | `200 List[NormalizedOperation]` |
| `GET /operations/{operation_id}` | None | `200 NormalizedOperation` |
| `POST /operations/{operation_id}/candidates/preview` | Generation options and finite candidate limit | `200 { "items": [TestCandidate], "persisted": false }` |

Import rules:
- Accept OpenAPI 3.x documents supported by the parser; report unsupported/invalid documents with `422 VALIDATION_ERROR` and actionable details.
- Store a bounded original document in PostgreSQL JSONB, plus content hash/version metadata. Reject oversized input before parsing/persistence.
- URL import uses the same SSRF-safe outbound boundary, with DNS and redirect revalidation, content-type/size/time limits, and no automatic remote reference resolution by the parser.
- The parser must not independently fetch external `$ref` URLs. External references are either rejected or treated according to a separately implemented bounded safe resolver; default behavior is reject unsupported remote refs.
- Candidate preview is deterministic by default, bounded, and non-persisting. It must not create test cases, executions, findings, or campaigns.
- Campaign creation persists the accepted generated candidate set and links each candidate to the source operation/specification version.

### 3.7 Health checks

| Method and path | Request | Success |
|---|---|---|
| `GET /projects/{project_id}/health-checks` | Pagination | `200 List[HealthCheckRead]` |
| `POST /projects/{project_id}/health-checks` | `HealthCheckCreate` | `201 HealthCheckRead` |
| `GET /health-checks/{check_id}` | None | `200 HealthCheckRead` |
| `PATCH /health-checks/{check_id}` | Partial editable check fields | `200 HealthCheckRead` |
| `DELETE /health-checks/{check_id}` | None | `204` |
| `POST /health-checks/{check_id}/run` | Optional bounded run overrides | `200 HealthCheckRunRead` |
| `GET /health-checks/{check_id}/runs` | Pagination | `200 List[HealthCheckRunRead]` |

Fixed MVP assertion types:
1. HTTP status code (exact or approved range/operator).
2. Latency threshold (`duration_ms`).
3. JSON path/value comparison.
4. Response header comparison.
5. Response schema validation.

Assertions must be explicit and serializable. A failed assertion means the configured check failed; it does not by itself prove a security vulnerability. Health checks use the same outbound target policy, response caps, redaction, and execution records as workspace requests.

### 3.8 Campaigns

| Method and path | Request | Success |
|---|---|---|
| `GET /projects/{project_id}/campaigns` | Pagination; optional state filter | `200 List[CampaignRead]` |
| `POST /projects/{project_id}/campaigns` | `CampaignCreate` | `202 CampaignRead` |
| `GET /projects/{project_id}/campaigns/{campaign_id}` | None | `200 CampaignRead` |
| `POST /projects/{project_id}/campaigns/{campaign_id}/cancel` | Empty body | `200 CampaignRead` |
| `GET /projects/{project_id}/campaigns/{campaign_id}/events` | `after` sequence and bounded `limit`, oldest-first | `200 List[CampaignEventRead]` |
| `GET /projects/{project_id}/campaigns/{campaign_id}/report` | None | `200 CampaignReport` |

The current create request accepts `name`, `generation_report_id`, `base_url`, optional same-project `environment_id` and `candidate_ids`, `baseline_by_operation`, `max_executions` (1–50), `max_iterations` (1–50), `max_duration_seconds` (1–600), and explicit `confirm_unsafe`. The report must belong to the project. Baseline maps use operation IDs and may include `path_parameters`, `query_parameters`, `headers`, and JSON `body` values, with a 2 MB total cap. Use environment placeholders such as `{{token}}` for secrets; the worker resolves them in memory and does not store resolved requests or response bodies. The API currently persists and queues selected candidates from an existing generation report.

Creation and durability:
- Before returning `202`, atomically persist the campaign, initial durable job, and initial event in one PostgreSQL transaction.
- A separate worker claims jobs transactionally using row locks and a lease/expiry model. The worker is not a second API service; it shares domain services and database contracts.
- The worker recovers expired leases. A case persisted as running when a lease expires is marked inconclusive and is not resent, avoiding blind replay after an uncertain network outcome.
- Execution is **not exactly-once**. If a process crashes after a request may have been sent but before its outcome was recorded, persist an uncertain outcome and do not blindly replay it.
- Retries are permitted only when failure is known to have happened before the target request was sent, subject to budgets.
- Budgets cap execution count, iterations, and elapsed time. Exhaustion terminates normally with state `completed` and a `budget_exhausted` termination reason.

State machine:

```text
queued -> running -> completed
   |         |-----> failed
   |         |-----> cancelled
   |         |-----> completed (budget exhausted)
   |         |-----> cancellation requested -> cancelled (cooperative)
   +----------------> cancelled
```

Terminal states are `completed`, `failed`, and `cancelled`; they cannot reopen. Cancelling a queued campaign moves it to `cancelled`. Cancelling a running campaign requests cooperative cancellation; the worker stops scheduling new work and records any in-flight outcome safely. Cancelling an already terminal campaign is idempotent and returns `200` with the unchanged current state.

Reports remain available for completed, failed, and cancelled campaigns. Partial evidence and findings are included when available. A campaign error must not erase already persisted evidence.

### 3.9 Findings and evidence

| Method and path | Request | Success |
|---|---|---|
| `GET /projects/{project_id}/findings` | Pagination; optional status/severity/classification/campaign filters | `200 List[FindingRead]` |
| `GET /findings/{finding_id}` | None | `200 FindingRead` |
| `PATCH /findings/{finding_id}` | Only user-managed triage fields, e.g. `{ "status": "reviewed", "severity": "high" }` | `200 FindingRead` |
| `GET /findings/{finding_id}/evidence` | Pagination | `200 List[EvidenceReferenceRead]` |
| `GET /evidence/{evidence_id}` | None | `200 EvidenceReferenceRead` |

- Evidence references retain provenance: `DECLARED`, `EXTRACTED`, `OBSERVED`, or `INFERRED`.
- Evidence links must identify their source execution, test, specification, knowledge fact, or other approved source relation.
- Excerpts are bounded and redacted. Do not expose unrestricted raw target response bodies through evidence endpoints.
- Findings must have traceable links to supporting executions/evidence. The classifier must distinguish observed facts from inferred hypotheses and explain uncertainty.
- `PATCH /findings/{finding_id}` must not let users rewrite system-generated provenance, evidence, classifier rationale, or execution results.

### 3.10 Reports

The canonical report route is `GET /campaigns/{campaign_id}/report`. It aggregates durable campaign, test, execution, finding, and evidence records. It is read-only and must enforce campaign/project ownership. A separate global reports endpoint is not part of the frozen MVP inventory unless approved through a contract change.

## 4. State, persistence, and consistency guarantees

- PostgreSQL is the system of record for users, sessions, projects, saved resources, specifications, normalized operations, executions, health checks, tests, campaigns, jobs, events, findings, and evidence references.
- All schema changes use Alembic migrations. `Base.metadata.create_all()` is not a migration strategy.
- Project-owned records must have an explicit project relationship or a verifiable ownership path through a parent record. Repository/service functions must not trust project IDs supplied by the client without checking ownership.
- Soft archive projects; preserve historical execution/campaign/evidence relationships. Do not expose permanent project deletion in MVP.
- `campaign_events` are append-only. Finding triage history is not a separate table in MVP; current user-managed status/severity are stored on the finding.
- Counts are derived from test/execution rows initially; avoid duplicated authoritative counters.
- Store immutable, redacted execution snapshots and relevant environment/specification version references.
- Store a bounded original OpenAPI JSON document with content hash/version metadata.
- Environment secrets are encrypted at rest and write-only at the API boundary.
- Response bodies and evidence excerpts have configurable retention and strict caps. Do not promise a retention duration until configured for the deployment.

## 5. Cross-module DTO ownership

| Contract | Accountable owner | Required collaboration |
|---|---|---|
| HTTP routes, error envelope, pagination, auth/session, project ownership | Developer A (integration lead) | Developer B reviews feature needs before route/schema changes |
| `RequestDefinition`, `ExecutionResult`, execution outcome semantics | Developer A | Developer B consumes the stable DTOs for candidate execution and analysis |
| `NormalizedOperation`, operation identity and source references | Developer B proposes/implements parser model; Developer A approves API/DB contract | Both agree before merging dependent work |
| `TestCandidate`, categories and preview semantics | Developer B | Developer A owns campaign persistence and API integration |
| `AssertionResult`, assertion vocabulary | Developer B owns analysis semantics; Developer A owns persistence/API wiring | Shared review for health and campaign integration |
| `FindingRead`, provenance, evidence link semantics | Shared: A owns persistence/API; B owns classifier rationale and evidence-producing analysis | Must be agreed before integration |
| `CampaignRead`, state machine, durable job/event contract | Developer A | Developer B plugs intelligence pipeline into the orchestrator without owning worker persistence |
| Generated TypeScript API types | Generated from FastAPI OpenAPI in CI | No manual edits; route/schema change requires regenerated output |

## 6. HTTP examples

### 6.1 Create a project

```http
POST /api/v1/projects
Content-Type: application/json
Cookie: session=<opaque-token>

{
  "name": "Payments API",
  "description": "Staging API regression checks"
}
```

```http
HTTP/1.1 201 Created
Content-Type: application/json

{
  "id": "6a4a9d7a-58d0-4a62-9f89-7f10e78c1111",
  "name": "Payments API",
  "description": "Staging API regression checks",
  "created_at": "2026-10-16T08:00:00Z",
  "updated_at": "2026-10-16T08:00:00Z",
  "archived_at": null
}
```

### 6.2 Preview candidates without persisting them

```http
POST /api/v1/operations/{operation_id}/candidates/preview
Content-Type: application/json

{
  "categories": ["positive", "negative", "boundary", "schema"],
  "limit": 20
}
```

```json
{
  "items": [],
  "persisted": false
}
```

The empty array above illustrates response shape only; it is not a claim that an implementation has generated candidates. The actual response contains generated candidate DTOs or returns a documented validation/operation error.

### 6.3 Create a campaign

```http
POST /api/v1/projects/{project_id}/campaigns
Content-Type: application/json

{
  "name": "Payments regression",
  "generation_report_id": "uuid",
  "base_url": "https://api.example.com",
  "baseline_by_operation": {"operation-id": {"path_parameters": {"id": "123"}}},
  "max_executions": 10,
  "max_iterations": 10,
  "max_duration_seconds": 120,
  "confirm_unsafe": false
}
```

Response: `202 Accepted` with `CampaignRead` in state `queued`. The campaign, initial job, and initial event must already be durable when the response is returned.

## 7. Implementation and verification requirements

A contract is not complete merely because a route exists. For every endpoint, implement and test:

1. Request validation and response schema.
2. Authentication and project ownership enforcement.
3. Correct status code and standard error envelope.
4. Persistence/transaction behavior and relevant foreign-key constraints.
5. Redaction and outbound security where applicable.
6. Pagination and deterministic ordering for list routes.
7. Unit tests for domain rules and PostgreSQL integration tests for ownership/persistence.
8. Generated OpenAPI and TypeScript contract update.

Minimum cross-feature acceptance flows:
- Google sign-in -> create project -> retrieve overview.
- Save request -> execute through safe transport -> retrieve history and redacted execution detail.
- Import OpenAPI file and URL safely -> inspect operations -> preview candidates without persistence.
- Create health check -> run each configured assertion type -> inspect run history.
- Create campaign -> durable job claim -> execute candidate -> classify/evidence -> cancel or finish -> retrieve report.
- Verify a second user's project/resource IDs cannot be accessed through any endpoint.
- Verify prohibited targets, DNS rebinding/redirect cases, timeouts, oversized bodies, and secret redaction.
- Verify migration from an empty PostgreSQL database and recovery of expired campaign-job leases.

## 8. Frozen decisions and change control

This file freezes the target contract as of 2026-10-16. Do not silently alter paths, status codes, DTO fields, state names, persistence semantics, or ownership rules. A contract change requires a PR that:

1. States the reason and compatibility impact.
2. Updates this file and `SOURCE_OF_TRUTH.md` or `DATABASE_SCHEMA.md` if affected.
3. Updates FastAPI/Pydantic schemas and tests.
4. Regenerates `apps/web/src/services/generated/api-schema.ts`.
5. Updates frontend service callers and integration tests.
6. Includes a migration if persistence changes.
7. Is reviewed by Developer A and the affected module owner.

Until a route is implemented, it remains a target contract. Use `IMPLEMENTATION_STATUS.md` to determine current implementation state.
