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
- [ ] PostgreSQL-backed deployment verification, real authentication, environment secret encryption/write-only responses, and cross-restart persistence.
- [~] Safe spec URL/docs-UI discovery is implemented in the API Explorer with bounded standard-path probing, Swagger UI config parsing, explicit choice for multiple matches, shared outbound SSRF controls, and redacted persisted source URLs. `$ref` resolution policy reporting remains incomplete; the discovery route still needs a passing async integration check.
- [~] Persisted candidates can run against an explicitly supplied base URL and baseline query/path/body/header values through the shared bounded executor. Each run has a distinct persisted execution report with actual status/timing/headers, optional status assertion, and non-confirming status/content-type/limited response-schema observations; JSON/Markdown/CSV exports and Request History reload are available. Response bodies and credentials are not stored. Rich response assertions, candidate validation/deduplication state, feedback policy, and full drift analysis remain incomplete.
- [~] Specification readiness analysis now checks operation summaries/IDs, response coverage, parameter schemas, request-body media/schema declarations, and server URLs. Results include JSON Pointer evidence, severity counts, scope/limitations, and a working Explorer action; two deterministic service tests pass. Analysis persistence, broader OpenAPI reference handling, and full route tests remain unverified.
- [ ] Campaign, findings, health-check, dedicated collection CRUD, and settings workflows connected to backend routes. Collection grouping currently uses a saved-request name field; unsupported screens use explicit empty states instead of sample records.
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
- `pytest tests/test_readiness.py tests/test_run_reports.py -q` — 5 passed (deterministic readiness, schema-mismatch privacy, skipped-reference, and Markdown export checks).
- Latest Ruff, Python syntax compilation, frontend typecheck/lint/production build, and `git diff --check` — passed after readiness and response-schema analysis changes.

## Git and environment

- Source reference: `D:\IntelAPI`, branch `master`, commit `d1fdcc0` at inspection.
- Target checkout remote: `https://github.com/ShukuNinja/IntelAPI.git`.
- User requested branch: `final-version`; no merge to `main`.
- Branch `final-version` is the delivery branch and is pushed to `origin/final-version`; no merge to `main` has been made.
- `D:\Pinnacle\.env` already exists and was left untouched and unread. The source checkout's `.env` was not copied or read. No new `.env` was created.
