# IntelAPI --- API Contracts

**Contract version:** 1.1\
**Baseline date:** 2026-10-18\
**Status:** Frozen target contract for implementation. This document
defines intended behavior; it does not claim that every endpoint is
already implemented.

**Authority and change control** - `SOURCE_OF_TRUTH.md` governs product
rules and cross-cutting decisions. - `DATABASE_SCHEMA.md` governs
persistence, relationships, constraints, and migrations. - This document
governs HTTP routes, wire DTOs, status codes, error semantics, and
API-level behavior. - If implementation conflicts with this contract, do
not silently change behavior. Submit a contract-change PR and update
affected documentation, schemas, tests, and migrations.

## 1. Contract-wide rules

### 1.1 Paths, encoding, and naming

-   The product API prefix is `/api/v1`.
-   Liveness and readiness probes are outside the versioned API:
    `GET /health/live` and `GET /health/ready`.
-   JSON requests and responses use `application/json`. OpenAPI file
    uploads use `multipart/form-data`; URL-based specification import
    uses JSON.
-   Timestamps are ISO 8601 UTC strings. Durations are integer
    milliseconds in fields named `duration_ms`.
-   Resource identifiers are UUIDs represented as strings. IDs are
    opaque; clients must not infer permissions or ownership from them.
-   JSON field names use `snake_case`.
-   Write DTOs should reject unknown fields. Response DTOs must not
    expose internal ORM fields, credential material, or fields not
    defined by the public contract.
-   FastAPI's generated OpenAPI schema is the machine-readable HTTP
    contract. Regenerate `apps/web/src/services/generated/api-schema.ts`
    from OpenAPI; never hand-edit the generated file.
-   Unless an endpoint explicitly specifies another response, successful
    list routes return the common pagination envelope in §1.4.

### 1.2 Authentication, authorization, and browser security

-   Every `/api/v1` endpoint requires a valid application session except
    `GET /api/v1/auth/google/config` and
    `POST /api/v1/auth/google/session`.
-   The backend verifies Google ID tokens, including signature, issuer,
    audience, expiry, and relevant claims. The stable Google `sub` is
    the identity key; email is not an identity key.
-   The backend issues an opaque, cryptographically random application
    session token. Only a cryptographic hash of the token is persisted.
-   The session is transported using an `HttpOnly` cookie. Production
    cookies must set `Secure`. Configure `SameSite` for the deployment
    topology.
-   State-changing cookie-authenticated requests must validate the
    allowed `Origin` and apply the selected CSRF defense.
-   Every project-owned resource must be authorized against the
    authenticated user's ownership on every read, write, import, and
    execution. Client-side route guards are not authorization.
-   Return `404 NOT_FOUND` for cross-owner resources where revealing
    existence would disclose information. Use `403 FORBIDDEN` when the
    resource is visible but the requested action is explicitly
    disallowed.
-   Never return secret environment-variable plaintext after writing it.
    Never log session tokens, Google ID tokens, secret values,
    authorization headers, or unredacted sensitive request/response
    content.

### 1.3 Standard error envelope

Application errors use the following shape:

``` json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request is invalid.",
    "details": [
      {
        "field": "name",
        "issue": "Field is required."
      }
    ]
  }
}
```

`details` is optional and may be an object or a list of field issues.
Clients branch on the stable `code`, not on human-readable message text.

  ------------------------------------------------------------------------------
                   HTTP status Error code                  Meaning
  ---------------------------- --------------------------- ---------------------
                           400 `BAD_REQUEST`               The request cannot be
                                                           interpreted.

                           401 `UNAUTHENTICATED`           The application
                                                           session is missing,
                                                           expired, or invalid.

                           403 `FORBIDDEN`                 The authenticated
                                                           user is not permitted
                                                           to perform the
                                                           action.

                           403 `TARGET_BLOCKED`            The outbound target
                                                           was rejected by
                                                           security policy
                                                           before an execution
                                                           could be recorded.

                           404 `NOT_FOUND`                 The resource is
                                                           absent or
                                                           intentionally hidden
                                                           due to ownership.

                           409 `CONFLICT`                  A uniqueness
                                                           constraint or state
                                                           transition conflicts
                                                           with current state.

                           413 `PAYLOAD_TOO_LARGE`         A request, response,
                                                           or imported
                                                           specification exceeds
                                                           a configured limit.

                           422 `VALIDATION_ERROR`          DTO or domain
                                                           validation failed.

                           429 `RATE_LIMITED`              A request, rate, or
                                                           execution budget
                                                           limit was exceeded.

                           502 `TARGET_CONNECTION_ERROR`   The target connection
                                                           failed before a
                                                           usable HTTP response
                                                           was received and no
                                                           execution result was
                                                           recorded.

                           504 `TARGET_TIMEOUT`            The target operation
                                                           timed out and no
                                                           execution result was
                                                           recorded.

                           500 `INTERNAL_ERROR`            An unexpected
                                                           server-side failure
                                                           occurred. Do not
                                                           expose stack traces.
  ------------------------------------------------------------------------------

**Execution distinction:** `POST /requests/execute` may return `200`
with an `ExecutionResult` whose `outcome` is `timeout`,
`connection_error`, `blocked_by_policy`, `response_too_large`, or
`execution_error` when the execution record was successfully created. A
validation, authentication, ownership, or pre-execution policy failure
that prevents creating an execution uses the standard HTTP error
envelope. Implement this distinction consistently.

### 1.4 Pagination and ordering

List endpoints accept: - `limit`: default `50`, minimum `1`, maximum
`100`. - `offset`: default `0`, minimum `0`.

Unless an endpoint defines a resource-specific ordering, results are
ordered newest first by `created_at`. Endpoints whose contract specifies
an alternate ordering must document it in OpenAPI.

List response:

``` json
{
  "items": [],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total": 0
  }
}
```

`total` is the count matching the filters before pagination. Lists must
be bounded; do not return unbounded collections.

### 1.5 Shared data and safety rules

-   IDs are UUID strings; timestamps are ISO 8601 UTC strings.
-   Secret values are write-only. Responses may expose
    `has_value: true|false`, never the secret itself.
-   Request snapshots, response excerpts, imported specifications,
    evidence excerpts, and logs are bounded and redacted according to
    configuration.
-   A target's non-2xx HTTP status is still an HTTP response; it is not
    a transport error.
-   An observation or unexpected response is evidence, not automatically
    a defect or vulnerability.
-   All outbound HTTP operations---including request execution,
    URL-based specification import, and health-check runs---must use the
    shared safe outbound boundary. No feature may introduce an alternate
    client that bypasses it.
-   Deterministic parsing, candidate generation, execution, and
    assertions must work without LLM credentials. LLM functionality is
    optional and cannot be the sole source of correctness.

## 2. Shared DTOs

The examples below describe semantic wire fields. Pydantic schemas and
generated OpenAPI must provide precise constraints, enum values, and
nullability without contradicting this contract. Optional and nullable
are distinct: an omitted field means "not supplied"; an explicit `null`
means "clear the value" only where the endpoint allows it.

### 2.1 User and project

``` json
{
  "UserRead": {
    "id": "uuid",
    "email": "user@example.com",
    "display_name": "User",
    "avatar_url": null,
    "created_at": "2026-10-16T08:00:00Z"
  },
  "ProjectCreate": {
    "name": "Payments API",
    "description": "Optional description"
  },
  "ProjectRead": {
    "id": "uuid",
    "name": "Payments API",
    "description": "Optional description",
    "created_at": "2026-10-16T08:00:00Z",
    "updated_at": "2026-10-16T08:00:00Z",
    "archived_at": null
  }
}
```

Project archive is soft deletion. The API does not expose permanent
project deletion in the MVP.

### 2.2 Collections

`CollectionCreate` contains `name` and optional nullable `description`.
`CollectionRead` contains `id`, `project_id`, `name`, `description`,
`created_at`, and `updated_at`.

A collection and all requests assigned to it must belong to the same
project. Deleting a collection must follow the database FK policy and
must not delete saved requests or execution history.

### 2.3 Saved request definition

A request body uses these supported `body_type` values:

-   `none`: no request body; `body` must be `null` or omitted.
-   `json`: a JSON value; `body` may be an object, array, scalar, or
    `null` where accepted by the schema.
-   `text`: a text payload.
-   `form_urlencoded`: form fields encoded as
    `application/x-www-form-urlencoded`.
-   `multipart`: multipart form fields/files, subject to the
    implementation's bounded upload policy.

`body_type` defaults to `none`. The implementation must define how each
body type is serialized and set the corresponding content type safely.
Callers cannot use a body type to bypass outbound policy or size limits.

The canonical request-definition shape is:

``` json
{
  "RequestDefinition": {
    "name": "Get account",
    "method": "GET",
    "url": "https://api.example.com/accounts/123",
    "headers": {
      "Accept": "application/json"
    },
    "query_params": {},
    "body": null,
    "body_type": "none",
    "environment_id": null
  }
}
```

Field semantics: - `name`: required for a saved request; a transient
execution may omit it if the endpoint schema allows that. - `method`:
required HTTP method, normalized consistently by the server. The
implementation must allow only supported methods. - `url`: required URL
template or absolute URL, resolved and validated before execution. -
`headers`: optional string-to-string map. Sensitive values are redacted
from logs and stored snapshots. - `query_params`: optional bounded map
of query parameter names to values. Repeated query values must be
represented consistently in the schema. - `body`: optional body value
governed by `body_type`. - `body_type`: one of `none`, `json`, `text`,
`form_urlencoded`, `multipart`. - `environment_id`: optional nullable
UUID referring to an environment in the same project. `null` means no
environment is selected.

A `SavedRequestRead` includes `id`, `project_id`, nullable
`collection_id`, `environment_id`, `name`, `method`, `url`, `headers`,
`query_params`, `body`, `body_type`, `created_at`, and `updated_at`. It
must not include resolved secret values.

**Environment behavior:** a saved request may reference an environment.
The environment must belong to the same project as the request. When an
environment is deleted, the reference is cleared
(`environment_id = null`); the request and execution history remain.
Environment substitution must be bounded, and resolved values must pass
the same URL, header, body, and outbound-target validation as literal
values.

**Saved request versus execution input:** the path
`POST /projects/{project_id}/requests` is authoritative for project
ownership; clients do not send a second `project_id` in its body. For
`POST /requests/execute`, the request may be transient or based on a
saved request. The endpoint's input schema must make the two modes
mutually exclusive and reject ambiguous combinations.

### 2.4 Execution results

``` json
{
  "ExecutionResult": {
    "id": "uuid",
    "outcome": "http_response",
    "status_code": 200,
    "duration_ms": 84,
    "response_headers": {
      "content-type": "application/json"
    },
    "body": {
      "excerpt": "{\"id\":123}",
      "truncated": false,
      "content_type": "application/json"
    },
    "transport_error": null,
    "started_at": "2026-10-16T08:00:00Z",
    "completed_at": "2026-10-16T08:00:00Z"
  }
}
```

`ExecutionResult.outcome` is one of: - `http_response` - `timeout` -
`connection_error` - `blocked_by_policy` - `response_too_large` -
`execution_error`

`status_code` is nullable and is populated only when an HTTP response
was received. An HTTP `4xx` or `5xx` response has
`outcome: "http_response"` and its actual status code.

The immutable execution snapshot contains the resolved method and URL,
safe headers, redacted body, and relevant environment/specification
version references. It must never contain plaintext secrets. Response
headers and body excerpts are allowlisted/bounded and redacted.
`transport_error` is a safe diagnostic description, not a raw exception
or stack trace.

### 2.5 API understanding and candidate DTOs

`SpecificationRead` exposes metadata such as `id`, `project_id`, `name`,
`content_hash`, version information, and timestamps. Raw specification
content is not returned by default.

`NormalizedOperation` includes `id`, `specification_id`,
`operation_key`, `method`, `path`, `summary`, `parameters`,
`request_body_schema`, `response_schemas`, `security_requirements`, and
timestamps where applicable. Normalized schemas describe the imported
specification; they do not prove that a target behaves as declared.

`TestCandidate` includes `id` (a preview candidate may use a transient
identifier), `operation_id`, `category`, `name`, `description`,
`request_template`, `expected_assertions`, `rationale`, `source_refs`,
and `confidence`. Categories are `positive`, `negative`, `boundary`,
`schema`, and `workflow`.

Candidate preview is bounded, deterministic by default, and
non-persisting. It does not create test cases, executions, findings, or
campaigns. Campaign creation persists the accepted candidate set and
links candidates to the source operation and specification version.

### 2.6 Assertions, findings, and evidence

-   `AssertionResult`: `id`, `execution_id`, `assertion_type`, `passed`,
    `expected`, `actual`, `message`, `created_at`.
-   `FindingRead`: `id`, `project_id`, `campaign_id`, `test_case_id`,
    `execution_id`, `title`, `description`, `classification`,
    `severity`, `status`, `confidence`, `created_at`, `updated_at`.
-   `EvidenceReferenceRead`: `id`, `finding_id`, `execution_id`,
    `source_type`, `provenance`, `summary`, `excerpt`, `created_at`.

`provenance` is one of `DECLARED`, `EXTRACTED`, `OBSERVED`, or
`INFERRED`.

Finding `status` and `severity` are user-managed triage fields where
exposed. Classification, provenance, execution results, and evidence
links are system-derived and cannot be silently overwritten through a
triage update.

### 2.7 Health-check DTOs

`HealthCheckCreate` defines a named, project-scoped check, a request
definition or saved-request reference, and a finite set of explicit
assertions. `HealthCheckRead` contains its ID, project association,
name, configuration, and timestamps. `HealthCheckRunRead` summarizes the
run, execution reference, assertion results, outcome, and timestamps.
Secret values are never returned in configuration or run DTOs.

Supported MVP assertion types: 1. HTTP status code: exact value or
approved range/operator. 2. Latency threshold using `duration_ms`. 3.
JSON path/value comparison. 4. Response-header comparison. 5.
Response-schema validation.

Assertions must be explicit and serializable. A failed assertion means
the configured check failed; it does not alone prove a security
vulnerability.

### 2.8 Campaign DTOs

`CampaignCreate` contains a name, a specification ID or explicit
operation selection, generation options, and finite budgets: -
`max_executions` - `max_iterations` - `max_elapsed_seconds`

The project is scoped by the route path. The API rejects missing/invalid
scope, invalid operation/specification relationships, non-positive
budgets, and budgets above policy.

`CampaignRead` contains `id`, `project_id`, `name`, `state`,
`created_at`, `started_at`, `completed_at`, `cancel_requested_at`, and a
bounded progress summary. States are `queued`, `running`, `completed`,
`failed`, and `cancelled`.

`CampaignReport` contains campaign metadata, aggregate counts derived
from test cases/executions, findings summary, execution outcomes,
budget/termination reason, and links or IDs to evidence. Do not maintain
duplicated authoritative counters unless a later contract decision
approves them.

## 3. Endpoint inventory

All paths in this section are relative to `/api/v1`. Unless explicitly
marked public, routes require an application session and applicable
ownership checks. List routes use the pagination rules in §1.4.

### 3.1 Authentication

  ---------------------------------------------------------------------------------------
  Method and path               Request                   Success
  ----------------------------- ------------------------- -------------------------------
  `GET /auth/google/config`     None                      `200 { "client_id": "..." }`;
                                                          public, no secret

  `POST /auth/google/session`   `{ "id_token": "..." }`   `200 UserRead`; sets
                                                          application session cookie

  `GET /auth/me`                None                      `200 UserRead`

  `POST /auth/logout`           None                      `204`; revokes current session
                                                          and clears cookie
  ---------------------------------------------------------------------------------------

Requirements: - Verify issuer, audience, signature, expiry, and relevant
claims for Google's ID token. - Never accept a client-supplied email as
proof of identity. - Store only the session token's cryptographic hash,
expiry, revocation state, and user reference. - Apply abuse controls and
security-relevant logging without logging credentials. - Validate origin
and CSRF defenses on state-changing cookie-authenticated routes.

### 3.2 Projects and overview

  -----------------------------------------------------------------------------------------
  Method and path                         Request                   Success
  --------------------------------------- ------------------------- -----------------------
  `GET /projects`                         Pagination; optionally    `200` paginated
                                          `include_archived=true`   `ProjectRead`
                                          if supported

  `POST /projects`                        `ProjectCreate`           `201 ProjectRead`

  `GET /projects/{project_id}`            None                      `200 ProjectRead`

  `PATCH /projects/{project_id}`          Partial `name`,           `200 ProjectRead`
                                          `description`

  `POST /projects/{project_id}/archive`   Optional                  `200 ProjectRead`
                                          `{ "archived": true }`;
                                          default archives

  `GET /projects/{project_id}/overview`   None                      `200 OverviewRead`
  -----------------------------------------------------------------------------------------

Archive is soft deletion (`archived_at` or the equivalent persisted
field). The MVP does not expose permanent project deletion. Archived
projects retain history; normal new work is rejected unless a later
accepted decision explicitly permits it. `OverviewRead` contains bounded
aggregate metrics and recent activity derived from persisted resources,
not frontend-generated mock data.

### 3.3 Collections

  ---------------------------------------------------------------------------------------------------------------------
  Method and path                             Request                                           Success
  ------------------------------------------- ------------------------------------------------- -----------------------
  `GET /projects/{project_id}/collections`    Pagination                                        `200` paginated
                                                                                                `CollectionRead`

  `POST /projects/{project_id}/collections`   `{ "name": "Regression", "description": null }`   `201 CollectionRead`

  `GET /collections/{collection_id}`          None                                              `200 CollectionRead`

  `PATCH /collections/{collection_id}`        Partial `name`, `description`                     `200 CollectionRead`

  `DELETE /collections/{collection_id}`       None                                              `204`
  ---------------------------------------------------------------------------------------------------------------------

The server derives the project from the authorized route/resource. A
collection can contain only requests from the same project. Deleting a
collection must not cascade-delete requests or execution history; follow
the FK behavior defined in `DATABASE_SCHEMA.md`.

### 3.4 Saved requests, execution, and history

  ----------------------------------------------------------------------------------------------
  Method and path                          Request                      Success
  ---------------------------------------- ---------------------------- ------------------------
  `GET /projects/{project_id}/requests`    Pagination; optional         `200` paginated
                                           `collection_id` filter       `SavedRequestRead`

  `POST /projects/{project_id}/requests`   Saved-request fields from    `201 SavedRequestRead`
                                           `RequestDefinition`,
                                           excluding `project_id`

  `GET /requests/{request_id}`             None                         `200 SavedRequestRead`

  `PATCH /requests/{request_id}`           Partial editable request     `200 SavedRequestRead`
                                           fields

  `DELETE /requests/{request_id}`          None                         `204`

  `POST /requests/execute`                 Exactly one of a transient   `200 ExecutionResult`
                                           request definition or        when an execution record
                                           saved-request reference,     is created
                                           with optional explicit
                                           overrides and
                                           `save_to_history`

  `GET /projects/{project_id}/history`     Pagination; optional         `200` paginated
                                           method/status/outcome/date   `ExecutionSummary`
                                           filters

  `GET /executions/{execution_id}`         None                         `200 ExecutionResult`
                                                                        with redacted snapshot
                                                                        metadata
  ----------------------------------------------------------------------------------------------

Execution requirements: - All target requests pass through the single
shared outbound execution service. - Enforce HTTP/HTTPS scheme policy,
host validation, DNS resolution and resolved-IP policy, redirect
revalidation, timeouts, request/response size limits, header limits, and
execution budgets. - Block loopback, private, link-local, reserved, and
other prohibited destinations by default. - Revalidate DNS and
destination policy on redirects and immediately before connecting to
mitigate DNS rebinding. Do not allow the HTTP client to follow redirects
without policy validation. - A target non-2xx response is returned as
`outcome: "http_response"` with its status code. - Capture bounded
response excerpts and selected safe headers; redact credentials and
sensitive values. - When `save_to_history=true`, persist the immutable
redacted execution snapshot and result. Campaign execution always
persists the required execution record. - Headers, environment
variables, redirects, or alternate HTTP clients must not bypass outbound
target policy. - The server validates that referenced saved requests,
collections, and environments belong to the same authorized project. -
If the environment referenced by a saved request is deleted, clear the
saved request's environment reference without deleting the request or
history.

### 3.5 Environments and variables

  --------------------------------------------------------------------------------------------------------------------------------------------------------------
  Method and path                                           Request                                                              Success
  --------------------------------------------------------- -------------------------------------------------------------------- -------------------------------
  `GET /projects/{project_id}/environments`                 Pagination                                                           `200` paginated
                                                                                                                                 `EnvironmentRead`

  `POST /projects/{project_id}/environments`                `{ "name": "Staging", "base_url": "https://staging.example.com" }`   `201 EnvironmentRead`

  `GET /environments/{environment_id}`                      None                                                                 `200 EnvironmentRead`; no
                                                                                                                                 secret plaintext

  `PATCH /environments/{environment_id}`                    Partial non-secret fields                                            `200 EnvironmentRead`

  `DELETE /environments/{environment_id}`                   None                                                                 `204`

  `PUT /environments/{environment_id}/variables/{key}`      `{ "value": "...", "is_secret": true }`                              `200 EnvironmentVariableRead`
                                                                                                                                 with `has_value`, never value

  `DELETE /environments/{environment_id}/variables/{key}`   None                                                                 `204`
  --------------------------------------------------------------------------------------------------------------------------------------------------------------

`EnvironmentRead` includes `id`, `project_id`, `name`, `base_url`, and
timestamps. `EnvironmentVariableRead` exposes the key, `is_secret`,
`has_value`, and safe metadata only; it never exposes the stored value.

Requirements: - Environments referenced by a saved request must belong
to the same project. - Secret values are encrypted at rest using a
server-side configuration key that is not stored alongside ciphertext in
the database. - A secret write response must not echo the submitted
value. - Resolver substitution is bounded and cannot bypass URL, header,
body, target, or execution policy. - Redact secret values from logs,
snapshots, errors, and evidence. - Deleting an environment clears
references from saved requests and executions where required by the
database contract; it does not delete saved requests or history.

### 3.6 OpenAPI specifications and operations

  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Method and path                                        Request                                                            Success
  ------------------------------------------------------ ------------------------------------------------------------------ --------------------------------------------------------
  `GET /projects/{project_id}/specifications`            Pagination                                                         `200` paginated `SpecificationRead`

  `POST /projects/{project_id}/specifications/import`    Multipart file upload **or** JSON                                  `201 SpecificationRead`
                                                         `{ "url": "https://.../openapi.json", "name": "Optional name" }`

  `GET /specifications/{specification_id}`               None                                                               `200 SpecificationRead` metadata; raw document only if
                                                                                                                            explicitly added to the contract

  `GET /specifications/{specification_id}/operations`    Pagination; optional method/tag filters                            `200` paginated `NormalizedOperation`

  `GET /operations/{operation_id}`                       None                                                               `200 NormalizedOperation`

  `POST /operations/{operation_id}/candidates/preview`   Generation options and finite candidate limit                      `200 { "items": [TestCandidate], "persisted": false }`
  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

Import requirements: - Accept supported OpenAPI 3.x documents. Invalid
or unsupported documents return `422 VALIDATION_ERROR` with actionable
details. - Reject oversized input before parsing or persistence. Store a
bounded original JSON document plus content hash/version metadata. - URL
import uses the same SSRF-safe outbound boundary, including DNS/redirect
revalidation and content-type, size, and time limits. - The parser must
not independently fetch external `$ref` URLs. Reject unsupported remote
references by default unless a separately reviewed, bounded safe
resolver is implemented. - Candidate preview is deterministic by
default, bounded, and non-persisting. It must not create test cases,
executions, findings, or campaigns. - Campaign creation persists the
accepted generated candidate set and links each candidate to its source
operation and specification version.

### 3.7 Health checks

  ------------------------------------------------------------------------------------------------
  Method and path                               Request                 Success
  --------------------------------------------- ----------------------- --------------------------
  `GET /projects/{project_id}/health-checks`    Pagination              `200` paginated
                                                                        `HealthCheckRead`

  `POST /projects/{project_id}/health-checks`   `HealthCheckCreate`     `201 HealthCheckRead`

  `GET /health-checks/{check_id}`               None                    `200 HealthCheckRead`

  `PATCH /health-checks/{check_id}`             Partial editable check  `200 HealthCheckRead`
                                                fields

  `DELETE /health-checks/{check_id}`            None                    `204`

  `POST /health-checks/{check_id}/run`          Optional bounded run    `200 HealthCheckRunRead`
                                                overrides

  `GET /health-checks/{check_id}/runs`          Pagination              `200` paginated
                                                                        `HealthCheckRunRead`
  ------------------------------------------------------------------------------------------------

The fixed MVP assertion types are: 1. HTTP status code: exact value or
approved range/operator. 2. Latency threshold (`duration_ms`). 3. JSON
path/value comparison. 4. Response-header comparison. 5. Response-schema
validation.

Assertions must be explicit and serializable. A failed assertion means
the configured check failed; it does not by itself prove a security
vulnerability. Health checks use the same outbound target policy,
response caps, redaction, and execution records as workspace requests.

### 3.8 Campaigns

  -------------------------------------------------------------------------------------------
  Method and path                             Request                 Success
  ------------------------------------------- ----------------------- -----------------------
  `GET /projects/{project_id}/campaigns`      Pagination; optional    `200` paginated
                                              state filter            `CampaignRead`

  `POST /projects/{project_id}/campaigns`     `CampaignCreate`        `202 CampaignRead`

  `GET /campaigns/{campaign_id}`              None                    `200 CampaignRead`

  `POST /campaigns/{campaign_id}/cancel`      Empty body              `200 CampaignRead`

  `GET /campaigns/{campaign_id}/tests`        Pagination              `200` paginated
                                                                      `TestCaseRead`

  `GET /campaigns/{campaign_id}/executions`   Pagination              `200` paginated
                                                                      `ExecutionSummary`

  `GET /campaigns/{campaign_id}/events`       Pagination; events      `200` paginated
                                              ordered oldest-first or `CampaignEventRead`
                                              by a documented cursor

  `GET /campaigns/{campaign_id}/report`       None                    `200 CampaignReport`
  -------------------------------------------------------------------------------------------

Durability and worker behavior: - Before returning `202`, atomically
persist the campaign, initial durable job, and initial event in one
PostgreSQL transaction. - A separate worker claims jobs transactionally
using row locks and a lease/expiry model. It shares domain services and
database contracts; it is not a second API service. - The worker
recovers expired leases after a crash. State transitions and event
writes are transactionally consistent where possible. - Execution is not
exactly-once. If a process crashes after a request may have been sent
but before the outcome is recorded, persist an uncertain outcome and do
not blindly replay it. - Retry only when failure is known to have
occurred before the target request was sent, subject to budgets. -
Budgets cap execution count, iterations, and elapsed time. Exhaustion
terminates normally as `completed` with a `budget_exhausted` event or
termination reason.

State machine:

``` text
queued -> running -> completed
   |         |-----> failed
   |         |-----> cancelled
   |         |-----> completed (budget exhausted)
   |         +-----> cancellation requested -> cancelled (cooperative)
   +---------------> cancelled
```

Terminal states are `completed`, `failed`, and `cancelled`; they cannot
reopen. Cancelling a queued campaign moves it to `cancelled`. Cancelling
a running campaign requests cooperative cancellation: the worker stops
scheduling new work and safely records any in-flight outcome. Cancelling
a terminal campaign is idempotent and returns `200` with its unchanged
state.

Reports remain available for completed, failed, and cancelled campaigns.
A campaign error must not erase already persisted evidence or findings.

### 3.9 Findings and evidence

  ---------------------------------------------------------------------------------------------------------------------------
  Method and path                         Request                                               Success
  --------------------------------------- ----------------------------------------------------- -----------------------------
  `GET /projects/{project_id}/findings`   Pagination; optional                                  `200` paginated `FindingRead`
                                          status/severity/classification/campaign filters

  `GET /findings/{finding_id}`            None                                                  `200 FindingRead`

  `PATCH /findings/{finding_id}`          Only user-managed triage fields,                      `200 FindingRead`
                                          e.g. `{ "status": "reviewed", "severity": "high" }`

  `GET /findings/{finding_id}/evidence`   Pagination                                            `200` paginated
                                                                                                `EvidenceReferenceRead`

  `GET /evidence/{evidence_id}`           None                                                  `200 EvidenceReferenceRead`
  ---------------------------------------------------------------------------------------------------------------------------

Requirements: - Evidence provenance is one of `DECLARED`, `EXTRACTED`,
`OBSERVED`, or `INFERRED`. - Evidence links identify an approved source:
execution, test, specification, knowledge fact, or other explicitly
supported relation. - Excerpts are bounded and redacted. Do not expose
unrestricted raw target response bodies through evidence endpoints. -
Findings link to supporting executions/evidence. The classifier
distinguishes observed facts from inferred hypotheses and communicates
uncertainty. - Finding triage updates cannot rewrite system-generated
provenance, evidence, classifier rationale, or execution results.

### 3.10 Reports

The canonical report endpoint is `GET /campaigns/{campaign_id}/report`.
It aggregates durable campaign, test, execution, finding, and evidence
records. It is read-only and enforces campaign/project ownership. A
separate global reports endpoint is not part of the frozen MVP inventory
unless approved through a contract change.

## 4. Persistence and consistency guarantees

-   PostgreSQL is the system of record for users, sessions, projects,
    collections, saved requests, environments, environment variables,
    specifications, normalized operations, executions, health checks,
    tests, campaigns, jobs, events, findings, and evidence references.
-   All schema changes use Alembic migrations.
    `Base.metadata.create_all()` is not a migration strategy.
-   Every project-owned record has an explicit project relationship or a
    verifiable ownership path through a parent record. Services must
    validate ownership; client-supplied project IDs are not trusted.
-   Project archive is soft deletion. Preserve historical execution,
    campaign, and evidence relationships. Do not expose permanent
    project deletion in the MVP.
-   `campaign_events` are append-only. Finding triage history is not a
    separate table in the MVP; current user-managed status/severity are
    stored on the finding.
-   Counts are derived from test/execution rows initially; avoid
    duplicated authoritative counters.
-   Persist immutable, redacted execution snapshots and relevant
    environment/specification version references.
-   Persist a bounded original OpenAPI JSON document with content
    hash/version metadata.
-   Environment secrets are encrypted at rest and write-only at the API
    boundary.
-   Response bodies and evidence excerpts have configurable retention
    and strict caps. Do not promise a retention duration until it is
    configured for the deployment.
-   Foreign-key deletion behavior must follow `DATABASE_SCHEMA.md`. In
    particular, deleting a collection must not delete saved requests or
    execution history; deleting an environment clears optional
    references rather than deleting requests or history.

## 5. Contract ownership

  ------------------------------------------------------------------------
  Contract area            Accountable owner       Required collaboration
  ------------------------ ----------------------- -----------------------
  HTTP routes, error       Developer A             Developer B reviews
  envelope, pagination,    (integration lead)      feature needs before
  auth/session, project                            route/schema changes
  ownership

  `RequestDefinition`,     Developer A             Developer B consumes
  `ExecutionResult`,                               stable DTOs for
  execution outcome                                candidate execution and
  semantics                                        analysis

  `NormalizedOperation`,   Developer B             Agree before dependent
  operation identity,      proposes/implements     work merges
  source references        parser model; Developer
                           A approves API/DB
                           contract

  `TestCandidate`,         Developer B             Developer A owns
  categories, preview                              campaign persistence
  semantics                                        and API integration

  `AssertionResult`,       Developer B owns        Shared review for
  assertion vocabulary     analysis semantics;     health-check and
                           Developer A owns        campaign integration
                           persistence/API wiring

  `FindingRead`,           Shared: A owns          Agree before
  provenance,              persistence/API; B owns integration
  evidence-link semantics  classifier rationale
                           and evidence-producing
                           analysis

  `CampaignRead`, state    Developer A             Developer B integrates
  machine, durable                                 intelligence pipeline
  job/event contract                               without owning worker
                                                   persistence

  Generated TypeScript API Generated from FastAPI  Never hand-edit;
  types                    OpenAPI in CI           route/schema changes
                                                   require regeneration
  ------------------------------------------------------------------------

## 6. HTTP examples

Examples are illustrative. UUIDs and response data are examples, not
guaranteed identifiers or current implementation output.

### 6.1 Create a project

``` http
POST /api/v1/projects
Content-Type: application/json
Cookie: session=<opaque-token>

{
  "name": "Payments API",
  "description": "Staging API regression checks"
}
```

``` http
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

### 6.2 Save a request

``` http
POST /api/v1/projects/{project_id}/requests
Content-Type: application/json
Cookie: session=<opaque-token>

{
  "name": "Get account",
  "method": "GET",
  "url": "https://api.example.com/accounts/123",
  "headers": {
    "Accept": "application/json"
  },
  "query_params": {},
  "body": null,
  "body_type": "none",
  "environment_id": null,
  "collection_id": null
}
```

The server obtains `project_id` from the route, checks ownership,
validates any collection/environment relationship, and returns
`201 SavedRequestRead`.

### 6.3 Preview candidates without persisting them

``` http
POST /api/v1/operations/{operation_id}/candidates/preview
Content-Type: application/json
Cookie: session=<opaque-token>

{
  "categories": ["positive", "negative", "boundary", "schema"],
  "limit": 20
}
```

``` json
{
  "items": [],
  "persisted": false
}
```

The empty array illustrates the response shape only. A real response
contains generated candidates or returns a documented
validation/operation error. Preview must not persist candidates or
create tests, executions, findings, or campaigns.

### 6.4 Create a campaign

``` http
POST /api/v1/projects/{project_id}/campaigns
Content-Type: application/json
Cookie: session=<opaque-token>

{
  "name": "Payments regression",
  "specification_id": "uuid",
  "operation_ids": ["uuid"],
  "generation_options": {
    "categories": ["positive", "negative", "boundary"]
  },
  "budgets": {
    "max_executions": 100,
    "max_iterations": 3,
    "max_elapsed_seconds": 600
  }
}
```

Return `202 Accepted` with `CampaignRead` in state `queued`. The
campaign, initial job, and initial event must already be durable when
the response is returned.

## 7. Implementation and verification requirements

A route is not complete merely because it exists. Each endpoint must
have tests for the applicable items below:

1.  Request validation and response schema.
2.  Authentication and project/resource ownership enforcement.
3.  Correct status code and standard error envelope.
4.  Persistence, transaction behavior, and relevant foreign-key
    constraints.
5.  Redaction and outbound security where applicable.
6.  Pagination and deterministic ordering for list routes.
7.  Domain unit tests and PostgreSQL integration tests for
    ownership/persistence.
8.  Generated OpenAPI and TypeScript contract updates.

Minimum cross-feature acceptance flows: - Google sign-in → create
project → retrieve overview. - Save request → execute through safe
transport → retrieve history and redacted execution detail. - Create an
environment and variables → select it for a saved request → execute with
safe substitution → verify no secret leaks. - Import an OpenAPI file and
URL safely → inspect operations → preview candidates without
persistence. - Create a health check → run each configured assertion
type → inspect run history. - Create campaign → durable job claim →
execute candidate → classify/evidence → cancel or finish → retrieve
report. - Verify a second user's project/resource IDs cannot be accessed
through any endpoint. - Verify prohibited targets, DNS
rebinding/redirect cases, timeouts, oversized bodies, and secret
redaction. - Verify migration from an empty PostgreSQL database and
recovery of expired campaign-job leases.

## 8. Frozen decisions and change control

This contract is frozen as version 1.1 with baseline date 2026-10-18. Do
not silently alter paths, status codes, DTO fields, enum values, state
names, persistence semantics, or ownership rules.

A contract-change PR must: 1. Explain the reason and compatibility
impact. 2. Update this document and `SOURCE_OF_TRUTH.md` or
`DATABASE_SCHEMA.md` when affected. 3. Update FastAPI/Pydantic schemas
and tests. 4. Regenerate
`apps/web/src/services/generated/api-schema.ts`. 5. Update frontend
service callers and integration tests. 6. Include an Alembic migration
if persistence changes. 7. Be reviewed by Developer A and the affected
module owner.

Until a route is implemented, it remains a target contract. Use
`IMPLEMENTATION_STATUS.md` to determine implementation state.