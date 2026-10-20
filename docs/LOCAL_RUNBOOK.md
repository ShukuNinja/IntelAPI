# IntelAPI â€” Local Development Runbook

**Refresh date:** 2026-10-19
**Primary environment:** Windows 10/11, PowerShell, Docker Desktop, Compose v2.
**Backend Python target:** Python 3.12 (see `apps/api/pyproject.toml`).

This runbook reflects the current repository layout. It does not imply that the full product workflow is implemented. See `IMPLEMENTATION_STATUS.md` and `M0_BASELINE_AUDIT.md` for the current status and verification boundaries.

## 1. Prerequisites

- Git
- Docker Desktop with Linux containers and Compose v2
- Node.js 22 for the container/CI-aligned frontend toolchain
- npm
- Python 3.12 if running backend checks outside Docker
- Access to the IntelAPI Git repository

Use the Compose PostgreSQL service for local development unless there is an explicit reason to use another database.

## 2. Refresh and inspect the baseline

```powershell
git switch main
git pull --ff-only origin main
git status --short
git rev-parse HEAD
git diff --check
docker compose config --services
```

Do not start a milestone from a dirty tree without first identifying and preserving the changes. Do not overwrite a working local `.env` without backing up its local-only values outside the repository.

## 3. Environment configuration

The root `docker-compose.yml` requires `POSTGRES_PASSWORD` in the root `.env` file. Copy the example only if no working local `.env` exists:

```powershell
Copy-Item .\.env.example .\.env
```

Review and replace example values with local-only secrets. Do not commit `.env`, OAuth credentials, provider keys, session/encryption keys, database dumps, or real user data. The API has an `apps/api/.env.example` as well; inspect settings and Compose configuration to determine which values are consumed from the root `.env` versus the API process.

`VITE_API_BASE_URL` is a Vite build-time variable. The current Docker web image does not configure it and has no `/api` reverse proxy. The frontend API client therefore defaults to same-origin, which is not yet a working API routing strategy in the current static-web container. This is a known integration gap; do not claim live frontend/API connectivity until a strategy is implemented and tested.

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

The metadata endpoint currently reports `status: scaffold` and is protected by the authenticated versioned router. If the request returns an authentication error, that is consistent with the current router configuration.

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

Run from the repository root:

```powershell
npm ci --prefix apps/web
npm run typecheck --prefix apps/web
npm run lint --prefix apps/web
npm run build --prefix apps/web
```

The frontend pages currently include demo fixtures. A successful typecheck/lint/build does not prove the UI is connected to real API data.

## 8. Security and data handling

- Do not paste or commit raw `.env` values, access tokens, session cookies, provider keys, Google credentials, database passwords, or private keys.
- All target API calls and URL-based specification imports must pass through the approved outbound-request boundary once implemented.
- Do not issue direct target requests from route handlers as a shortcut.
- Do not execute generated candidates without validation and explicit execution.
- Inspect `docker compose config` output locally before sharing it; environment interpolation can expose secret values.
- Do not run `docker compose down -v` unless you intentionally want to destroy the local database volume and have confirmed the data is disposable.

## 9. Working on a milestone

```powershell
git switch main
git pull --ff-only origin main
git switch -c feat/short-task-name
```

After a scoped change:

```powershell
git diff --check
git status --short
git diff --stat
```

Run relevant tests and quality checks, commit only intended files, push the feature branch, and open a PR. Do not push feature work directly to `main` or force-push shared branches.

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

Check the browser Network panel, `VITE_API_BASE_URL`, API logs, CORS origins, and cookie settings. The current static-web container does not proxy `/api`; same-origin fallback is not sufficient without a proxy. Do not solve cookie/CORS problems by allowing all origins with credentials.

## 11. When reporting a failure

Include the current commit hash, `git status --short`, exact command, relevant sanitized logs, Docker/database health, and whether the failure reproduces on latest `main`. Never include secret values.
