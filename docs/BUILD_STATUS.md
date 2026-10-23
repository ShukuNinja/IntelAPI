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
- [ ] PostgreSQL-backed deployment verification, real authentication, saved requests, and cross-restart persistence.
- [~] Safe spec URL/docs-UI discovery is implemented in the API Explorer with bounded standard-path probing, Swagger UI config parsing, explicit choice for multiple matches, shared outbound SSRF controls, and redacted persisted source URLs. `$ref` resolution policy reporting remains incomplete; the discovery route still needs a passing async integration check.
- [~] Persisted candidates can now be run against an explicitly supplied base URL and baseline query/path/body values through the shared bounded executor; execution outcomes are recorded without storing credentials or response bodies. Candidate validation, feedback policy, response assertions, drift/readiness analyzers, and execution reports/exports remain incomplete.
- [ ] Campaign, findings, health-check, collection, environment, and settings workflows connected to backend routes. Unsupported screens use explicit empty states instead of sample records.
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
- Alembic `upgrade head` — passed against a fresh in-memory SQLite database including migration `0006`.
- Latest frontend typecheck, lint, and production build — passed after connecting candidate execution controls.
- The new discovery and source-URL changes pass Python syntax compilation and Ruff. Focused pytest invocations stalled before completing under the current local Python/async test runner, including a pre-existing async executor test; earlier 35-test, migration, and frontend checks were completed before these latest changes.

## Git and environment

- Source reference: `D:\IntelAPI`, branch `master`, commit `d1fdcc0` at inspection.
- Target checkout remote: `https://github.com/ShukuNinja/IntelAPI.git`.
- User requested branch: `final-version`; no merge to `main`.
- Branch `final-version` is the delivery branch and is pushed to `origin/final-version`; no merge to `main` has been made.
- `D:\Pinnacle\.env` already exists and was left untouched and unread. The source checkout's `.env` was not copied or read. No new `.env` was created.
