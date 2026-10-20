# IntelAPI â€” M0 Baseline Audit Record

**Audit date:** 2026-10-19
**Audited snapshot identifier:** `fc87b1012b943e7b946a1ce6889941ae6e74305c`
**Purpose:** freeze the post-merge source baseline, capture evidence-backed implementation status, and define repeatable local verification before M1 begins.

## 1. Inputs and method

- Inspected the tracked source/configuration archive supplied as `IntelAPI-main-audit(2).zip`.
- Inspected API route registration, FastAPI application setup, SQLAlchemy models, Alembic revision files, frontend route/pages, frontend API client, Vite config, Docker Compose, Dockerfiles, package scripts, and GitHub Actions workflow.
- Did not inspect live GitHub Actions runs, the user's local database state, a running Docker stack, browser behavior, real provider credentials, or production traffic.

## 2. Repository inventory

| Component | Location | Observed role |
|---|---|---|
| Backend API | `apps/api/app/main.py`, `apps/api/app/api/` | FastAPI app, auth, project routes, metadata, health probes |
| Persistence | `apps/api/app/models/`, `apps/api/app/db/`, `apps/api/alembic/` | SQLAlchemy models, session setup, Alembic migrations |
| Intelligence | `apps/api/app/modules/` | OpenAPI normalization, knowledge extraction, generation, validation, adaptive scoring, assertions, classification, LLM orchestration and preview |
| Provider adapter | `apps/api/app/integrations/llm/` | Provider interface, factory, NVIDIA Build adapter |
| Frontend | `apps/web/src/` | React/Vite app, pages, shared components, API client and demo fixtures |
| Local infrastructure | `docker-compose.yml`, `apps/api/Dockerfile`, `apps/web/Dockerfile` | PostgreSQL, API and static web containers |
| CI | `.github/workflows/ci.yml` | Frontend typecheck/lint/build; backend PostgreSQL migration, Ruff, mypy and pytest |
| Canonical docs | `docs/` | Product decisions, schema/contract, implementation plan/status and runbook |

## 3. Confirmed implementation observations

1. The FastAPI router registers authentication, project, and metadata routers. Health endpoints are registered separately in `main.py`.
2. Authentication routes exist for Google configuration, Google session creation, current user, and logout.
3. Project routes exist for list, create, retrieve, patch, and archive.
4. SQLAlchemy models and migrations exist for users, projects, sessions, collections, environments, environment variables, and saved requests.
5. Intelligence source modules exist for OpenAPI parsing/normalization, knowledge extraction, candidate generation/validation/deduplication, adaptive scoring, assertion analysis, classification, optional LLM orchestration, candidate preview, and the NVIDIA provider.
6. The API router does not register public routes for workspace CRUD, specification import, candidate preview, outbound execution, request history, health-check management, campaigns, findings/evidence, or reports.
7. The frontend contains product pages and shared components, but several pages import `demoData.ts`; live end-to-end data flow is not complete.
8. The frontend API client falls back to same-origin `/api/...`; the current Vite config has no proxy, and the web Docker image serves static assets without configuring `VITE_API_BASE_URL` at build time.
9. `.gitignore` did not cover all nested Python bytecode/cache and Python package metadata artifacts. The supplied archive includes tracked artifacts that should be removed from the repository.
10. The migration revision chain in the archive is `0001_initial` â†’ `0002_identity_projects` â†’ `ba3a950852cf` â†’ `0003_workspace_assets`.

## 4. Important gaps and decisions

### G-01 â€” Frontend API URL strategy

**Observed:** the client supports `VITE_API_BASE_URL`, but the current Docker web build does not pass it and no reverse proxy routes `/api` to the API service.

**Decision for M0:** do not silently rely on same-origin behavior. For local direct-origin development, configure `VITE_API_BASE_URL=http://localhost:8000` at Vite build/dev time. If the deployment uses same-origin cookies and `/api`, introduce an explicit reverse-proxy configuration and test it. Choose and implement the actual strategy in M1 before connecting the frontend.

### G-02 â€” Workspace persistence without API surface

**Observed:** models/migrations exist, but router registration does not expose collection/environment/request CRUD.

**Decision for M1:** implement the workspace service/API against existing models and the accepted contract; do not create duplicate tables or bypass Alembic.

### G-03 â€” Intelligence modules without product workflow

**Observed:** intelligence modules and focused tests exist, but there are no registered API routes for specification import or candidate preview.

**Decision for M3:** expose the existing module through a thin service/API layer after persistence and the safe import boundary are established. Keep candidate preview non-persisting and deterministic fallback available.

### G-04 â€” No safe outbound execution service found

**Observed:** no shared production HTTP execution service was found in the audited implementation.

**Decision:** do not add a direct `httpx` call to an API route or frontend action as a shortcut. Build one shared outbound security boundary before any real target API request is sent.

### G-05 â€” Generated artifacts tracked

**Observed:** tracked Python cache/bytecode and `*.egg-info` artifacts are included in the supplied archive.

**Decision:** broaden `.gitignore`, then remove already tracked generated artifacts with `scripts/cleanup_tracked_artifacts.ps1`. Review the resulting staged deletions before committing.

## 5. Local verification commands

Run from the repository root in Windows PowerShell after refreshing `main` and applying the M0 file changes. Use Python 3.12 / the API container for backend checks. These are commands to run; this document does not claim their results in the user's local environment.

```powershell
# Git baseline
 git status --short
 git rev-parse HEAD
 git diff --check

# Compose configuration and services
docker compose config --services
docker compose config

docker compose up --build -d
docker compose ps
docker compose logs --tail 100 api
docker compose logs --tail 100 db
docker compose logs --tail 100 web

# API health and database migration state
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
Invoke-RestMethod http://localhost:8000/api/v1/meta
docker compose exec api alembic heads
docker compose exec api alembic current
docker compose exec api alembic check

# Backend quality gates
docker compose exec api ruff check .
docker compose exec api mypy app
docker compose exec api pytest -q

# Frontend quality gates
npm ci --prefix apps/web
npm run typecheck --prefix apps/web
npm run lint --prefix apps/web
npm run build --prefix apps/web

# Review final change set
git status --short
git diff --check
git diff --stat
```

If `ruff`, `mypy`, or `alembic check` is unavailable in the running API container, inspect the installed dependency set and use the repository's supported environment; do not silently skip the check. `docker compose config` can expand environment values, so do not paste its raw output anywhere without checking it for secrets.

## 6. M0 exit criteria

M0 is complete when:

- the working tree is based on the latest `main` and the commit hash is recorded;
- current implementation status and local run instructions match the repository;
- generated artifacts are untracked and ignored;
- the frontend API URL strategy and its current implementation gap are documented;
- health, migration, backend quality, and frontend quality checks have recorded outcomes;
- unresolved failures are recorded with exact command, error, and ownership rather than being marked passed.

## 7. Follow-on order

1. **M1:** auth/project frontend integration and workspace CRUD/secret storage.
2. **M2:** secure outbound HTTP execution and persisted request history.
3. **M3:** specification persistence/import and candidate preview API.
4. **M4:** health checks, assertions, findings, evidence, and reports.
5. **M5:** durable campaign/job worker and adaptive execution orchestration.
6. **M6:** end-to-end integration, security hardening, clean-build verification, and release documentation.
