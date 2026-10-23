# Build status

Status checked 2026-10-24. This is an operational checklist; a checked item requires code and a passing check.

## Implemented and verified in this workspace

- [x] Backend liveness and existing project/user ORM scaffold copied from IntelAPI.
- [x] Parse OpenAPI 3.0.x/3.1.x JSON/YAML and Swagger 2.0 JSON/YAML; normalize operations, inherit path parameters, and enforce a 2 MB content cap (16 focused tests passed).
- [x] Produce deterministic, explainable schema-based candidate previews with operation-scoped IDs and request/report budgets.
- [x] Generate endpoint-wise reports (maximum 100 operations and 500 candidates), persist candidate IDs/reasons/validation state, reopen reports, and export JSON/Markdown/CSV.
- [x] Local single-user project and specification persistence endpoints, deduplication, reload endpoint, Alembic migration, and SQLite route tests. Migrations from an empty SQLite database passed; PostgreSQL runtime persistence is not verified.
- [x] Explorer UI creates/selects a project, imports JSON/YAML files or pasted content, saves and reloads stored specifications/reports, browses actual operations, previews candidates, and downloads report exports. Frontend typecheck/lint/build pass.
- [x] Shared outbound executor supports bounded HTTP/HTTPS requests, DNS destination validation and IP pinning, loopback development targets, denied private/reserved targets by default, disabled redirects/proxies, timeouts, response limits, and unsafe-method confirmation. Workspace displays real responses and project-scoped execution history; execution metadata migration added. A real loopback fixture request passed.
- [~] Project-scoped saved requests, named environments, collection grouping, CRUD routes, request-builder controls, and `{{variable}}` interpolation are implemented. Migration 0008 and route coverage are added; run-path HTTP integration remains unverified because the local TestClient portal hangs at startup.
- [~] Environment secret values are encrypted with Fernet, returned as names-only metadata, resolved server-side for executions, and lazily migrated from legacy environment rows. Focused encryption/write-only migration tests pass. PostgreSQL runtime, key rotation, real authentication, and cross-restart verification remain open.
- [~] Safe spec URL/docs-UI discovery is implemented in the API Explorer with bounded standard-path probing, Swagger UI config parsing, explicit choice for multiple matches, shared outbound SSRF controls, and redacted persisted source URLs. `$ref` resolution policy reporting remains incomplete; the discovery route still needs a passing async integration check.
- [~] Persisted candidates can run against an explicitly supplied base URL and baseline query/path/body/header values through the shared bounded executor. Each run has a distinct persisted execution report with actual status/timing/headers, optional status assertion, user-defined checks for allowlisted response headers and JSON Pointer presence/type, non-confirming status/content-type/limited response-schema observations, and `feedback-rules-v1` bounded follow-up proposals; proposals never auto-execute. JSON/Markdown/CSV exports and Request History reload are available. Response bodies and credentials are not stored. Equality checks against arbitrary response-body values, candidate validation state, campaign-wide budgets, and full drift analysis remain incomplete.
- [~] Specification readiness analysis now checks operation summaries/IDs, response coverage, parameter schemas, request-body media/schema declarations, and server URLs. Results include JSON Pointer evidence, severity counts, scope/limitations, and a working Explorer action; two deterministic service tests pass. Analysis persistence, broader OpenAPI reference handling, and full route tests remain unverified.
- [~] Explicit feedback branches stop after transport outcomes, failed assertions, contract observations, or incomplete schema checks; otherwise they propose prior-unrun candidate IDs within a 0–20 per-report suggestion budget. Campaign execution now has independent execution/iteration/time budgets; feedback proposals still require user execution.
- [~] Campaigns persist selected candidate test cases, queued jobs, leases, and append-only events; a separate Compose worker sends bounded requests through the shared executor, records status/timing-only results, supports cooperative cancellation, and exposes progress/report/event APIs. The Campaigns UI can create and inspect runs. SQLite campaign creation/request-builder tests pass; a live worker/PostgreSQL run is not verified on this machine. Finding classification/evidence attachment from campaign results and durable crash-recovery runtime verification remain incomplete.
- [~] Findings & Evidence derives review items from persisted contract observations and failed assertions, with durable per-observation human triage (confirmed, false positive, accepted) and optional notes. Health checks have persisted definitions/runs, read-only saved-request execution, deterministic status/latency/header/JSON Pointer/schema assertions, and a connected history UI. Dedicated collection CRUD and settings workflows remain incomplete. Collection grouping currently uses a saved-request name field.
- [ ] Full E2E, Docker Compose, database restart persistence, security tests, and evaluation benchmarks.

## Verification

- `python -m compileall -q app tests` — passed (Python 3.13 syntax compilation).
- `apps/api/.venv/Scripts/python.exe -m pytest -q` — 35 passed using isolated SQLite/model fixtures and a real local HTTP fixture; 1 upstream Starlette/httpx deprecation warning.
- `DATABASE_URL=sqlite+pysqlite:///:memory: alembic upgrade head` — passed from an empty SQLite database.
- `apps/api/.venv/Scripts/ruff.exe check app tests alembic` — passed.
- `npm run typecheck` — passed.
- `npm run lint` — passed.
- `npm run build` — passed (Vite production build completed).
- `docker compose config --services` — passed; services resolved as `db`, `api`, `web`.
- `docker compose ps` — unavailable: Docker Desktop Linux engine is not running. PostgreSQL runtime persistence has not been verified.
- `git diff --check` — passed.
- Alembic `upgrade head` — passed against a fresh in-memory SQLite database including migrations `0006` through `0008`.
- Latest frontend typecheck, lint, and production build — passed after connecting candidate execution reports, request saving, and environment controls.
- Current Ruff and Python compile checks passed. Focused pytest invocation still stalls before making an HTTP request: faulthandler shows Starlette TestClient waiting while starting AnyIO's Windows event-loop portal/socket pair; no latest route integration test result is available. Earlier 35-test suite passed before the current discovery, candidate report, and saved-resource changes.
- `pytest tests/test_feedback_policy.py tests/test_readiness.py tests/test_run_reports.py -q` — 12 passed (feedback branches/bounds, readiness evidence, schema-mismatch privacy, skipped-reference, and Markdown export checks).
- Latest Ruff, Python syntax compilation, frontend typecheck/lint/production build, and `git diff --check` — passed after readiness and response-schema analysis changes.
- The response assertion feature adds safe allowlisted-header and JSON Pointer presence/type checks; focused policy/readiness/report tests passed (14 tests). Frontend typecheck, lint, and production build passed after the assertion UI changes.
- Findings triage tests — 2 passed, including persistence/update behavior with SQLite; total focused test group is 16 passed. Ruff, compileall, migration `0009` upgrade against fresh in-memory SQLite, frontend typecheck/lint/build, and `git diff --check` passed. Route-level TestClient integration remains unverified because the Windows AnyIO portal hangs before requests are issued.
- Health-check assertion and run-history unit tests pass with SQLite; migration `0010` upgrades a fresh SQLite database. Full health-check HTTP route integration remains unverified due to the same Windows AnyIO event-loop socket-pair hang in the local TestClient environment.
- Environment-secret and campaign focused tests: 4 passed using in-memory SQLite; campaign tests cover atomic campaign/job/event/test creation and request mutation building. A worker loop integration test could not start an asyncio event loop because this Windows Python environment blocks in the standard-library socket-pair accept path; no live target request was attempted by that test.
- Ruff, compileall, frontend typecheck/lint/production build, and Alembic upgrade through `0012_campaigns` on a fresh SQLite database passed after campaign UI/worker changes. Docker Compose PostgreSQL and worker runtime remain unverified because Docker Desktop is unavailable.

## Git and environment

- Source reference: `D:\IntelAPI`, branch `master`, commit `d1fdcc0` at inspection.
- Target checkout remote: `https://github.com/ShukuNinja/IntelAPI.git`.
- User requested branch: `final-version`; no merge to `main`.
- Branch `final-version` is the delivery branch and is pushed to `origin/final-version`; no merge to `main` has been made.
- `D:\Pinnacle\.env` already exists and was left untouched and unread. The source checkout's `.env` was not copied or read. No new `.env` was created.
