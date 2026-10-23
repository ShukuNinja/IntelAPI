# IntelAPI â€” Local Development Runbook

**Refresh date:** 2026-10-21
**Primary environment:** Windows 10/11, PowerShell, Docker Desktop, Compose v2.
**Backend Python target:** Python 3.12 (see `apps/api/pyproject.toml`).

This runbook describes the integrated MVP on `frontend-backend_integration`. See `COMPLETION_LOG.md` for current verification and remaining acceptance boundaries. `M0_BASELINE_AUDIT.md` is a historical baseline record.

## 1. Prerequisites

- Git
- Docker Desktop with Linux containers and Compose v2
- Node.js 22 for the container/CI-aligned frontend toolchain
- npm
- Python 3.12 if running backend checks outside Docker
- Access to the IntelAPI Git repository

Use the Compose PostgreSQL service for local development unless there is an explicit reason to use another database.

## 2. Inspect the active integration branch

```powershell
git branch --show-current
git status --short
git rev-parse HEAD
git diff --check
docker compose config --services
```

Keep work on `frontend-backend_integration` for this project task. Do not merge it into `main`. Identify and preserve existing local changes before editing. Do not overwrite a working local `.env` or expose its local-only values.

## 3. Environment configuration

The root `docker-compose.yml` requires `POSTGRES_PASSWORD` in the root `.env` file. Copy the example only if no working local `.env` exists:

```powershell
Copy-Item .\.env.example .\.env
```

Review and replace example values with local-only secrets. Do not commit `.env`, OAuth credentials, provider keys, session/encryption keys, database dumps, or real user data. The API has an `apps/api/.env.example` as well; inspect settings and Compose configuration to determine which values are consumed from the root `.env` versus the API process.

For Groq generation, set `LLM_PROVIDER=groq`, `GROQ_API_KEY`, and an active `GROQ_MODEL` in the root `.env`. The current default is `openai/gpt-oss-120b`. `LLM_GENERATION_MAX_ATTEMPTS` controls transient-error retries (default 2, maximum 3); schema-validation 400s are not retried. Experiment setup lets you request 1–10 LLM candidates per operation (default 4). Groq retired `llama-3.3-70b-versatile` for free and developer plans on August 16, 2026; after changing provider settings, recreate the API service so it reloads the environment. Provider keys stay server-side.

`VITE_API_BASE_URL` is a Vite build-time variable. Compose builds the web app with `http://localhost:8000` by default, so browser API calls go directly to the local API service. The API CORS configuration permits the local web origin and credentialed requests. If you change the local ports or origins, update the Vite build argument and API `CORS_ORIGINS` together, then rebuild the web image.

## 4. Start and inspect the stack

```powershell
docker compose config --services
docker compose up --build -d
docker compose ps
docker compose logs --tail 100 api
docker compose logs --tail 100 db
docker compose logs --tail 100 web
```

Expected container ports in the current Compose file:

- API: `http://localhost:8000`
- Web: `http://localhost:5173`
- PostgreSQL: internal Compose service `db` (not published to the host by default)

A healthy container only proves that its health check passes. It does not prove the full product workflow works.

## 5. Verify API and migrations

```powershell
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
Invoke-RestMethod http://localhost:8000/api/v1/meta

docker compose exec api alembic heads
docker compose exec api alembic current
docker compose exec api alembic check
```

The versioned metadata endpoint is authenticated; an authentication error before sign-in is expected. The liveness and readiness probes are public.

Do not use `Base.metadata.create_all()` to bypass migrations. All schema changes require reviewed Alembic revisions. Test migrations against PostgreSQL, not only SQLite. Do not drop/reset the database as routine troubleshooting.

## 6. Backend quality gates

Run in the API container, which is built from `apps/api`:

```powershell
docker compose exec api ruff check .
docker compose exec api mypy app
docker compose exec api pytest -q
```

The API image copies source into the image and does not bind-mount host source. After host-side source edits, rebuild/recreate the API container before testing those changes:

```powershell
docker compose build api
docker compose up -d api
```

If a tool is missing from the container, inspect the dev dependency installation and use the repository-supported environment rather than silently skipping the gate.

## 7. Frontend quality gates

Run from the repository root. Compose supplies `VITE_API_BASE_URL` as a build argument. For a standalone local Vite server or build, set it to the host API origin first:

```powershell
npm ci --prefix apps/web
$env:VITE_API_BASE_URL = "http://localhost:8000"
npm run typecheck --prefix apps/web
npm run lint --prefix apps/web
npm run build --prefix apps/web
```

The integrated feature pages call the API and use persisted project data. Typecheck, lint, and build checks do not prove authenticated user flows, which require a signed-in browser session. If the browser reports an HTML response where JSON is expected, confirm that the build-time `VITE_API_BASE_URL` points to the API origin rather than the web origin.

## 8. Security and data handling

- Do not paste or commit raw `.env` values, access tokens, session cookies, provider keys, Google credentials, database passwords, or private keys.
- All target API calls and URL-based specification imports pass through the shared outbound-request boundary.
- Do not issue direct target requests from route handlers as a shortcut.
- Do not execute generated candidates without validation and explicit execution.
- Inspect `docker compose config` output locally before sharing it; environment interpolation can expose secret values.
- Do not run `docker compose down -v` unless you intentionally want to destroy the local database volume and have confirmed the data is disposable.

## 9. Working on a milestone

```powershell
git branch --show-current
git status --short
```

After a scoped change:

```powershell
git diff --check
git status --short
git diff --stat
```

Run relevant tests and quality checks, commit only intended files, and keep this integration work on its feature branch. Do not switch to or merge into `main` for this task.

## 10. Troubleshooting

### Docker daemon unavailable

Start Docker Desktop, wait for the engine to become ready, then run `docker info` and `docker compose ps`. Do not debug application code until Docker is healthy.

### API container exits

```powershell
docker compose ps
docker compose logs --tail 200 api
docker compose config
```

Check missing environment variables, import/dependency errors, migration state, and database connectivity.

### Database unhealthy

```powershell
docker compose logs --tail 200 db
docker compose exec api alembic current
```

Inside the API container, the database host must be the Compose service name (`db`), not `localhost`.

### Browser requests fail

Check the browser Network panel, the built `VITE_API_BASE_URL`, API logs, allowed CORS origins, and cookie settings. Local development uses a direct API origin; do not solve cookie/CORS problems by allowing all origins with credentials.

## 11. When reporting a failure

Include the current commit hash, `git status --short`, exact command, relevant sanitized logs, Docker/database health, and whether the failure reproduces on latest `main`. Never include secret values.
