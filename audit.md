# IntelAPI Branch Audit and Implementation Plan

**Branch:** `final-version`  
**Audit started:** 2026-10-24  
**Scope:** Intended product architecture, current API/web/database implementation, security boundaries, operational setup, CI, tests, and remaining delivery work.  
**Audit mode:** Implementation and verification of the research prototype requested in the attached brief.

## Completion log

| Step | Status | Record |
|---|---|---|
| 1. Confirm branch and repository state | Complete | Repository is `IntelAPI`; branch is `final-version`; starting tree was clean at commit `5619dbe`. |
| 2. Extract intended architecture and acceptance gates | Complete | Product source of truth, API contracts, schema, phased implementation gates, and definition of done reviewed. |
| 3. Inventory and inspect current implementation | Complete | Reviewed API/web routes, ORM models/migrations, outbound execution, campaign worker, findings, CI, tests, and implementation/status docs. |
| 4. Compare implementation with intended scope | Complete | Feature matrix below distinguishes implemented, partial, and missing work against source-of-truth and acceptance gates. |
| 5. Write prioritized completion plan and final audit | Complete | Prioritized implementation sequence and verification gates recorded below. |

## Implementation completion log

| Step | Status | Record |
|---|---|---|
| 1. Confirm request scope and preserve existing workspace | Complete | User brief explicitly supersedes the audit-only scope: implement the local research prototype; retain `final-version`, existing database data, local-only binding, and no auth work. Existing untracked `audit.md` preserved and extended. |
| 2. Implement experiment persistence and semantic backend | Complete | Added experiment-run model/migration, deterministic rule extractor, provenance facts, scored selection, generation/execution/comparison/export APIs, and bounded local `$ref` resolver. Full backend tests and Ruff passed. |
| 3. Build workbench frontend | Complete | Added navigation/page, spec import, both generation actions, separate execution budget, metrics/charts, fact and rationale inspection, history retrieval, and comparison export. Frontend typecheck/lint/build passed. |
| 4. Add controlled benchmark and experiment tests | Complete | Added deterministic localhost endpoint with seeded response-schema defect and focused parser/semantic/persistence tests. Backend suite: 73 passed; live Compose migration and app services verified. |
| 5. Close critical audited gaps | Complete for agreed local prototype scope | Added Collections/Environments management UI, project update/archive and aggregate overview APIs/UI, and enabled CI on `final-version`. Authentication and first-class findings/evidence remain explicitly outside this local prototype slice and are retained as release work. |
| 6. Run, verify, document, and report actual result | Complete | Latest Compose images rebuilt; PostgreSQL migration at head; live browser generated/executed both approaches, then refreshed and successfully reloaded each persisted run from history. Run evidence is below. |
| 7. Audit project lifecycle across the whole UI | Complete | Added a persistent app-wide project selector and always-visible create action; routed every project-scoped screen through one shared project state and persisted the selection locally. Switching projects clears scoped selections/results to prevent stale data from being used in another project. |
| 8. Close imported-spec execution handoff | Complete | Saved-spec import/list/detail responses now expose safe HTTP server URLs (credentials/query/fragment stripped); Workbench uses that server and shows per-operation baseline keys. Regression coverage verifies URL sanitization. |
| 9. Rebuild and verify updated application | Complete | Full backend suite: 73 passed; frontend typecheck, lint, and production build passed. Compose API, worker, and web containers rebuilt; live browser confirmed the global selector, create action, and create form. |

## Executive summary

This branch is a substantial local MVP of the intended API testing product: it has persisted project/workspace resources, OpenAPI parsing and discovery, bounded outbound HTTP, candidate generation and execution reports, health checks, and a PostgreSQL-backed campaign worker. The remaining work is concentrated in production identity/tenancy, product surfaces that are still placeholders, durable finding/evidence provenance, and release-grade end-to-end/security verification.

The current design is correctly a **modular monolith with one separate worker**, not a collection of microservices. The main release blockers are: no authentication/session implementation; a deliberate local-single-user identity and production-mode guard rather than real multi-user ownership; Collections and Environments pages that explicitly say their UI persistence is not connected despite backend resources and Workspace controls existing; Settings still a placeholder; no dedicated project overview API; findings are observations reconstructed from report JSON rather than first-class findings/evidence records; and CI does not run on `final-version`.

## Follow-up workflow audit — 2026-10-24

The cross-application project gap is now closed for the local single-user workflow: create and switch projects from the global sidebar or header on every route, with the same selected project reflected in Explorer, Workbench, requests, health checks, campaigns, findings, collections, and environments. Selection survives refresh. Project-scoped results/selections are reset during switching so an old report or saved request cannot accidentally be applied under a different project. The existing project list and create API remain the persistence authority; no authentication was added.

The Workbench import handoff is also connected: stored specifications provide safe HTTP server base URLs and stable operation IDs for baseline input. Relative or non-HTTP server templates are not proposed as executable targets. URLs containing credentials, query parameters, or fragments are sanitized before being returned for convenience.

Remaining application gaps from the broader architecture audit are still tracked above: auth/tenancy for production, evidence persistence/provenance, settings/integrations, API contract consistency, and broader browser E2E and security coverage. These are separate from the project-switching workflow and were not silently marked complete.

This was a source and documentation audit. No test suite was run as part of this request. Existing test files were inspected; runtime checks previously observed in this session are not a substitute for release verification.

## Intended architecture

The accepted design is a **modular monolith**, not a set of microservices:

1. **React/Vite/TypeScript browser client** calls `/api/v1` over same-origin or a configured API base and presents project-scoped request, specification, health-check, campaign, and evidence workflows.
2. **FastAPI application** owns HTTP validation, identity/authorization, domain orchestration, shared outbound request policy, and API error/DTO contracts.
3. **PostgreSQL** stores users/sessions, projects, workspace assets, specifications and operations, executions/assertions, campaigns/jobs/events, findings, and evidence references. Alembic is the schema authority.
4. **Separate campaign worker process** claims durable PostgreSQL jobs under leases, invokes the same domain/execution services as the API, and persists state transitions/events. It must not provide a second target HTTP transport.
5. **Target APIs** are reached only through a shared outbound boundary that enforces scheme/IP/DNS/redirect, timeout, body-size, execution-budget, and redaction controls. OpenAPI parsing itself must not fetch remote `$ref`s.

The product promise is reproducible, evidence-backed API testing that works without LLM credentials. Deterministic candidates/assertions are the baseline; optional LLM assistance may enrich, but cannot bypass validation or security. The release gate also requires project ownership, bounded persistence, actionable reports, frontend end-to-end flows, and CI/migration/security coverage.

## Audit inventory and feature status

| Capability | Current branch status | Audit notes |
|---|---|---|
| App and deployment foundation | Implemented for local stack | FastAPI, React/Vite, PostgreSQL, Alembic, Docker Compose, and a separate worker are present. Prior session successfully brought up the local API/DB/web stack and applied migrations; this audit did not repeat that run. |
| Identity and sessions | Missing | `User` model exists, but no login/OAuth verification, opaque sessions, logout/current-user, CSRF flow, or browser auth state. App shell advertises single-user mode. |
| Project ownership | Partial/local-only | Project/resource routes use a fixed `intelapi-local-single-user` principal. A production-mode guard rejects local-only project operations. This is suitable only for the stated local MVP, not authenticated multi-user deployment. |
| Projects and specifications | Partial | Create/list projects; import/list/get specifications; parser/normalization exists. No project read/update/archive lifecycle. Specs and operations are chiefly stored as JSON document data rather than normalized operation/fact provenance records. |
| API Workspace | Implemented, with gaps | Manual request execution, saved requests, collections, environments, execution history are wired through Workspace. The simple Collections and Environments routes still render “persistence is not implemented” and do not provide standalone management flows. |
| Outbound execution safety | Substantially implemented | Shared executor validates HTTP(S), rejects URL credentials, resolves/validates addresses, pins a resolved address, disables redirects and environment proxies, requires unsafe-method confirmation, and bounds time/body/headers/response. Discovery uses this boundary. Needs production-grade adversarial/rebinding and integration validation; explicit concurrency control and end-to-end request redaction evidence remain release gates. |
| OpenAPI understanding/discovery | Partial-to-implemented baseline | JSON/YAML parsing, normalization, candidate generation, URL discovery of docs/spec endpoints, and readiness routes exist. Need verify document-size/operation caps and `$ref` behavior against all accepted requirements, and provide better provenance/contract coverage. |
| Candidate generation and reports | Partial | Deterministic candidate preview, candidate execution, generation/execution report reads and exports, assertions/contract observations, and follow-up suggestions exist. Large logic resides in a very large router; no separately modeled knowledge-fact/provenance subsystem or optional LLM adapter was found. The LLM adapter is optional, but extraction/provenance still forms part of the product promise. |
| Health checks | Implemented baseline | Persistent checks, safe saved-request selection, fixed assertion types, execution, and run history are present. Needs full acceptance coverage and UX/error-state review. |
| Durable campaigns | Implemented baseline; needs hardening verification | PostgreSQL jobs, leases, worker, events, cancellation, budgets, interrupted-test handling, reports, and shared executor are present. Delivery is at-least-once around dispatch; code marks interrupted in-flight cases inconclusive instead of blindly replaying. Prove restart/cancel races, lease expiry, concurrent workers, and partial reports with PostgreSQL integration tests. |
| Findings and evidence | Partial | Findings are reconstructed from the newest execution-report JSON and triage is persisted separately. There are no first-class Finding/EvidenceReference models or immutable evidence records/provenance chain as specified. API list is capped at 200 reports without a pagination contract. |
| Overview | Partial | Frontend aggregates data by loading projects and then per-project specs/executions. No dedicated overview/aggregate endpoint was found; this is N+1 and does not provide the intended campaign/findings outcome metrics. |
| Collections / Environments / Settings UI | Partial or missing | Workspace supports collection/environment operations, but the dedicated pages are explicitly unconnected placeholders. Settings is placeholder copy; integrations/preferences are not implemented. |
| API contract and error/pagination consistency | Partial | Endpoints exist, but many routers construct dict DTOs inline and return plain lists. Canonical shared response/error/pagination contracts and generated TypeScript schema are not fully represented in the current frontend workflow. |
| CI and release verification | Partial | CI runs frontend typecheck/lint/build and backend migration/lint/mypy/pytest with PostgreSQL, but triggers only on `main`/`develop`, not `final-version`. No frontend unit/E2E test jobs or generated API-type drift gate. |
| Documentation/status | Needs correction | `IMPLEMENTATION_STATUS.md` labels its old scaffold as historical, but retains obsolete path/commit and claims Docker unavailable; that conflicts with current branch and the successful local Compose run seen in-session. Refresh it after implementation milestones. |

## Architecture explanation

The intended user journey is: create a project → configure a target/environment or import an OpenAPI contract → inspect parsed operations and readiness → preview deterministic positive/negative/boundary/schema/workflow candidates → explicitly run a request or enqueue a bounded campaign → persist execution metadata and assertions → present explainable observations with evidence/provenance → triage and export a report. A user must be able to do the deterministic workflow without an LLM key.

At runtime the browser calls the versioned FastAPI API. API routes validate inputs and project scope, use SQLAlchemy/Alembic-managed PostgreSQL for durable state, and call domain services. Ordinary requests, health checks, remote specification discovery, and campaign execution converge on the shared outbound execution service. Campaign creation persists jobs; the separate worker claims jobs using database row locks and expiring leases, runs at most bounded work, and records state/events. This separation keeps long work out of request handlers while preserving durable progress. The current implementation follows much of this shape; identity, explicit domain/repository boundaries, evidence persistence, and some frontend surfaces are incomplete.

## Findings and risks

1. **Release blocker — no identity/session layer.** The accepted design requires Google identity verification and hashed application sessions. Current routes use a fixed local principal and some operations are disabled under production settings. Do not treat this branch as a multi-user deployment until login, session lifecycle, CSRF protections, and server-enforced per-user/project ownership are implemented and tested.
2. **High — evidence is not first-class.** The UI and findings route derive observations from execution report JSON; triage is separate. There is no durable evidence-reference graph to immutable execution/request/spec versions. This limits traceability and later re-evaluation.
3. **High — CI omits this branch.** `.github/workflows/ci.yml` only targets `main` and `develop`; pushes/PRs to `final-version` do not receive the configured checks. Add the release branch (or an appropriate wildcard/reusable workflow) before relying on branch CI.
4. **High — key UI workflows are incomplete.** Dedicated Collections and Environments routes say persistence is not implemented, despite backend endpoints and Workspace forms. Settings is also a placeholder. This makes implemented resources hard to discover/manage and fails the intended product destinations.
5. **Medium — overview/API contract gaps.** Overview does client-side fan-out rather than a dedicated aggregate endpoint. Routes commonly return plain lists and inline dictionaries, with inconsistent pagination/error DTO enforcement and no verified generated API schema drift gate.
6. **Medium — domain layering and maintainability.** Business logic and DTO construction are concentrated in routers, notably test generation. Extract service/schema boundaries incrementally while keeping API behavior stable; avoid a broad rewrite.
7. **Medium — campaign correctness needs database-backed proof.** The implementation includes leases, recovery markers, event sequencing, budgets, and cancellation, but these concurrency/restart semantics need PostgreSQL integration tests. Treat interrupted network dispatch as uncertain/inconclusive, not exactly-once.
8. **Medium — operational docs are stale.** Current status/runbook metadata and historical scaffold claims are confusing. Update status, runbook, and branch CI notes with exact current evidence; do not overwrite historical facts without labeling them.
9. **Low/medium — encoded database password is a manual operational footgun.** Current Compose supports `POSTGRES_PASSWORD_URL_ENCODED` for reserved URL characters, but the raw and encoded values must remain synchronized. Prefer constructing the connection URL safely in configuration or document the required encoding precisely.

## Implementation plan (recommended sequence)

| Phase | Work | Exit gate |
|---|---|---|
| 0. Branch/release hygiene | Include `final-version` in CI; refresh status/runbook against current branch; verify clean migrations on PostgreSQL from empty DB. | Branch receives CI; docs identify exact branch/commit and known test outcomes. |
| 1. Identity and ownership | Implement Google token validation, opaque hashed sessions, login/logout/current-user, browser session state and CSRF protections; replace fixed local identity with authenticated project ownership on every resource/action. Preserve local-only mode explicitly for development. | Cross-user read/write/execute isolation tests pass; auth/session security tests pass. |
| 2. Contracts and domain boundaries | Add shared Pydantic request/response models, standard error envelope and cursor/page pagination; extract business logic from routers to module services; generate TypeScript API types and add drift check. | OpenAPI contract is stable, typed client matches it, and API pagination/error tests pass. |
| 3. Complete workspace destinations | Build Collections and Environments management pages on existing endpoints; add project get/update/archive lifecycle and project selection; implement or remove/define Settings scope. Add dedicated overview aggregate API and replace client fan-out. | Browser can complete project/resource workflows without hidden Workspace-only controls; overview metrics match persisted state. |
| 4. Evidence and findings | Introduce first-class findings/evidence references with immutable links to spec/version, candidate, request snapshot, execution, assertion, and provenance; add retention/redaction rules and report aggregation. Keep observations distinct from confirmed defects. | Every displayed observation can be traced to persisted evidence; classification and export survive restart. |
| 5. Intelligence completeness | Verify parser size/operation/reference constraints; persist normalized operation/version and knowledge facts with source/provenance; round out candidate categories/deduplication and deterministic scoring. Add optional provider adapter only behind validated interface if in accepted MVP. | Parser/candidate corpus tests pass; no remote `$ref` fetch; deterministic baseline remains usable offline. |
| 6. Campaign and outbound hardening | Add PostgreSQL tests for concurrent workers, lease expiry/reclaim, crash before/after dispatch, cancellation races, budgets, partial reports, and event order. Add DNS rebinding/redirect/private-IP/header-secret/oversize/time budget tests; enforce concurrency caps. | Security and durability invariants have repeatable automated coverage; no claim of exactly-once delivery. |
| 7. Frontend and release gate | Add frontend tests and E2E flows for auth/project, workspace/history, import/preview, campaign/report, findings/evidence; test loading/error/empty states and accessibility. Add CI gates for tests, E2E where supported, migrations, schema drift, and branch coverage. | Full required workflow succeeds from fresh PostgreSQL and clean browser state; docs/runbook align with the verified build. |

Implement phases in dependency order. Phase 1 is a deployment gate; phases 3–5 can be staged after auth groundwork, and phase 6 should run continuously alongside feature development. Avoid introducing microservices or new infrastructure for this scope.

## Audit verification and limits

- Reviewed source-of-truth, API contract, database schema, ownership/phase plan, implementation status, and local runbook documents.
- Inspected current backend route decorators, ORM model inventory, Alembic migration inventory, frontend router/pages, Docker/Compose wiring, CI workflow, campaign worker/service, shared execution/discovery, and findings persistence approach.
- Inspected existing tests by module; did not run tests or alter application code in this audit.
- The starting checkout was clean at `5619dbe` on `final-version`. A previous turn in this session brought up the local application and observed healthy API/database plus the overview UI; that is a local smoke observation, not a full acceptance run.
- This audit was followed by an implementation pass; the completion log above supersedes the earlier audit-only status. Runtime-specific caveats are listed below.

## Implementation result and remaining work (2026-10-24)

The local research-prototype slice is implemented on `final-version`. The API now persists deterministic experiment runs, extracts semantic facts with source provenance without an LLM, selects candidates using explainable scores, executes bounded experiments through the shared outbound transport, and compares/exports results. A local seeded Widget API provides one deterministic response-schema defect for controlled evaluation. The Workbench supports creating/selecting a project, importing the fixture, generation and execution of both approaches, metrics, semantic fact inspection, run history, and comparison export.

Other high-priority gaps addressed in this pass: project lifecycle and aggregate overview API, usable Collections and Environments management pages, and CI triggers for `final-version`. Existing application and database state was preserved; migrations were applied to the existing PostgreSQL database. The app stack runs with API/web ports bound to localhost.

### Verification record

- Backend: `pytest -q` — 73 passed, 3 warnings (Starlette/httpx deprecation and SQLite foreign-key teardown warnings).
- Backend style/syntax: Ruff check passed; Python compileall passed; `git diff --check` passed.
- Frontend: typecheck, lint, and production build passed.
- Runtime: Compose API, worker, web, and PostgreSQL services healthy; Alembic reports `0014_experiment_runs (head)`.
- Not fully verified: full production identity/session ownership; first-class immutable findings/evidence records; PostgreSQL campaign crash/concurrency properties; strict mypy (still reports existing repository typing gaps). The workbench's seeded benchmark is a local controlled example, not a general effectiveness result.
- Live browser run: created project `Codex Research Prototype Demo`, imported `IntelAPI Seeded Defect Benchmark 3.1.0`, generated/executed contract run `97e4e5fe-7581-40dc-8d00-ef8c4cde255c` and semantic run `9392a6bb-3730-47ee-8729-4d45be59f797`. Each selected/executed 3 candidates, reported one seeded defect detected, and showed 100% operation/constraint coverage for this one-operation fixture. Each also had one inconclusive required-parameter omission and one expected invalid-boundary failure. After reloading the page, both runs appeared in persisted history and selecting them restored their metrics/outcomes. The sample verifies workflow persistence, not comparative statistical performance.

### Remaining implementation plan

1. Add authentication/session lifecycle, CSRF protections, and server-enforced per-user ownership before any multi-user deployment.
2. Add first-class finding/evidence models linked to immutable spec, candidate, request, execution, and assertion provenance.
3. Add PostgreSQL integration coverage for campaign concurrency/recovery and outbound boundary adversarial cases.
4. Add browser E2E coverage for import, experiment execution, history reload, resource CRUD, and overview; exercise refresh persistence in the running stack.
5. Resolve strict mypy errors and add frontend/API contract drift coverage so all configured CI gates pass reliably.

This remains a local research prototype. No login, multi-user production authorization, or claim of general benchmark quality is implied by the implemented vertical slice.

