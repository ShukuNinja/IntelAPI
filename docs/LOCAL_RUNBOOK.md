# IntelAPI — Local Development Runbook

**Audience:** Developer A and Developer B
**Baseline date:** 2026-10-24
**Primary OS assumed:** Windows 10/11 with PowerShell and Docker Desktop. Linux/macOS users should translate shell syntax and report any platform-specific difference.

This runbook describes the runnable local demo. Google sign-in and production multi-user authorization are not implemented; run with the development defaults only on a trusted local machine.

## 1. Prerequisites

- Git
- Docker Desktop with Linux containers and Compose v2
- Node.js version compatible with the checked-in `engines` field; the last reported environment used Node `v24.19.0`
- npm; the last reported environment used pnpm `v12.10.1`, but the verified frontend commands below use npm
- Python version specified in `apps/api/pyproject.toml` / Dockerfile
- Access to the IntelAPI Git repository

Do not install PostgreSQL separately if the Compose PostgreSQL service is the intended local database.

## 2. Clone and inspect

```powershell
git clone https://github.com/ShukuNinja/IntelAPI.git
cd IntelAPI
git switch final-version
git pull --ff-only origin final-version
git status --short
```

The canonical development path used for this delivery is `D:\Pinnacle`; your clone path can differ.

Before running commands, inspect the current scripts and service names:

```powershell
Get-Content .\compose.yaml
Get-Content .\apps\web\package.json
Get-Content .\apps\api\pyproject.toml
```

If the Compose file is named `docker-compose.yml` or another supported filename, use the actual checked-in filename consistently.

## 3. Environment configuration

1. Locate the checked-in `.env.example` files and copy the appropriate example to the local ignored `.env` file expected by Compose.
2. Fill only required local values. Use a local-only database password. To store environment secrets, set `ENVIRONMENT_ENCRYPTION_KEY` to a stable Fernet key generated with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Keep the same key across restarts and backups; losing it makes stored secrets unreadable.
3. Do not copy your teammate's `.env`, paste secrets into chat/PRs, or commit `.env`.
4. Confirm `.gitignore` excludes `.env`, local overrides, test artifacts, and database volumes.
5. Google sign-in requires a configured Google client ID only after auth implementation is integrated. Ordinary deterministic API workspace and candidate generation must not require an LLM key.

Typical PowerShell pattern (adjust the source filename to the repository's actual example):

```powershell
Copy-Item .\.env.example .\.env
```

Never overwrite a working `.env` without backing up its local-only values outside the repository.

## 4. Start the stack

From the repository root:

```powershell
docker compose up --build -d
docker compose ps
docker compose logs --tail 100 api
docker compose logs --tail 100 worker
docker compose logs --tail 100 web
```

If service names differ, get the exact names from `docker compose config --services`.

Expected baseline:
- API available at `http://localhost:8000`
- Web client available at `http://localhost:5173`
- PostgreSQL healthy in Compose

Open the web app in a browser at `http://localhost:5173`.

Apply schema migrations before using the workspace:

```powershell
docker compose exec api alembic upgrade head
```

The Compose `worker` service processes queued campaigns. It shares the API image and database; it must be running for campaign jobs to advance from `queued`.

## 4.1 Demo path

### Research workbench (local deterministic experiment)

The workbench compares two offline, reproducible candidate-selection approaches against the same imported API contract. It does not require an LLM key. The optional seeded target is served by the API itself and is only intended for local experimentation.

1. Open **Experimental Workbench** from the navigation or visit `http://localhost:5173/workbench`.
2. Create/select a project, then use **Load local seeded benchmark** and **Import specification** to add the small Widget API contract.
3. Keep the target base URL at `http://localhost:8000/api/v1/research-benchmark`. The fixture includes a controlled response type defect for widget `13`; the other responses are the baseline controls.
4. Run both candidate-generation approaches. Review their selected candidates, selection rationale, semantic facts, and coverage metrics.
5. Execute both with the same bounded execution budget. Compare detection metrics and individual outcomes. Generation is offline; HTTP requests happen only after the explicit execution action.
6. Reload each saved run from **History** to confirm persistence, then export the comparison as JSON or Markdown.

The backend stores experiment configurations and results, but redacts parameter/header values from stored configuration. Do not use real secrets or production targets in this prototype. The experiment comparison describes results for the selected contract and budget; it is not a general performance claim.

### Existing API workflow

1. Open **API Explorer**, create a project, and import a small OpenAPI JSON/YAML file or paste a document.
2. Generate a candidate report and confirm the endpoints and candidate ideas are visible.
3. Open **Campaigns**, choose the project and report, enter a reachable target base URL, and set a small execution budget.
4. For operations with path parameters or JSON request bodies, add baseline values keyed by the operation IDs shown in the form. Example: `{ "operation-id": { "path_parameters": { "id": "123" }, "body": { "name": "demo" } } }`.
5. Queue the campaign. The worker runs candidate requests through the same destination, redirect, timeout, and response-size protections as the request workspace. Review its progress, test results, and event timeline on the Campaigns page.

Use a local mock API target only when `ALLOW_LOCAL_TARGETS=true` in the API environment. State-changing methods are not sent unless the campaign creation checkbox explicitly confirms them.

## 5. Verify API and database

```powershell
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
Invoke-RestMethod http://localhost:8000/api/v1/meta
docker compose exec api alembic current
docker compose exec api pytest -q
```

Current limitations: Google authentication and production multi-user authorization are not implemented; first-class evidence records and full end-to-end browser acceptance tests remain open. The research benchmark is a controlled localhost fixture, not a general-purpose benchmark. The environment key must remain stable across restarts or stored secrets cannot be decrypted.

These are baseline smoke checks, not acceptance tests for the full product.

## 6. Frontend install and checks

```powershell
npm ci --prefix apps/web
npm run typecheck --prefix apps/web
npm run lint --prefix apps/web
npm run build --prefix apps/web
```

If the repository uses pnpm workspace commands instead, inspect `package.json` and `pnpm-workspace.yaml`, then use the checked-in scripts. Do not change the package manager or regenerate lockfiles without Developer A's approval.

Known audit note from the baseline: frontend dependencies had 7 audit findings in older Tailwind 3 transitive dependencies. Do not run `npm audit fix --force`; propose a controlled dependency update with visual/build regression checks.

## 7. Useful development commands

```powershell
# Current service state
docker compose ps

# Tail logs
docker compose logs -f api
docker compose logs -f web
docker compose logs -f db

# Restart a service after configuration/code changes
docker compose restart api

# Rebuild after Dockerfile or dependency changes
docker compose up --build -d

# Run backend tests
docker compose exec api pytest -q

# Check migration head/current revision
docker compose exec api alembic current
docker compose exec api alembic heads
```

Use `docker compose config --services` to discover exact service names. A service may be named `postgres` rather than `db`.

## 8. Database and migrations

- All schema changes require Alembic revisions authored/merged by Developer A.
- Never use `Base.metadata.create_all()` to bypass migrations.
- Before adding a migration, inspect the revision graph and latest `head`.
- Do not create two independent migration heads. Coordinate with Developer A before pulling a branch that changes schema.
- Run migration integration tests against PostgreSQL, not only SQLite, before declaring persistence work complete.
- Do not drop/reset the database unless you explicitly intend to destroy local data.

For a disposable local database only, stop the stack and remove volumes only after confirming that you do not need the stored data:

```powershell
docker compose down
# DESTRUCTIVE: removes local Compose volumes and database contents.
docker compose down -v
```

Do not run `down -v` as a routine troubleshooting command.

## 9. Working on your assigned branch

```powershell
git switch main
git pull --ff-only
git switch -c feat/your-short-task-name
git status --short
```

After implementing a scoped task:

```powershell
# Run the relevant tests and checks first
git diff --check
git status --short
git diff --stat
git add <explicit-files>
git commit -m "feat: describe the scoped change"
git push -u origin feat/your-short-task-name
```

Open a PR. Do not push directly to `main`, force-push shared branches, commit `.env`, or include unrelated lockfile/formatting changes. PR requirements and file permissions are defined in `IMPLEMENTATION_PLAN_AND_OWNERSHIP.md`.

## 10. Troubleshooting

### Docker daemon unavailable
- Start Docker Desktop.
- Wait until the engine reports ready.
- Run `docker info` and `docker compose ps`.
- Do not troubleshoot application code until Docker is healthy.

### Port already in use
- Inspect the process bound to ports 8000/5173 and the Compose port mappings.
- Stop the conflicting local process or coordinate a port change; do not silently change committed defaults.

### API container exits
```powershell
docker compose ps
docker compose logs --tail 200 api
docker compose config
```
Check missing environment variables, import errors, migration state, and dependency installation.

### Database is unhealthy / API cannot connect
```powershell
docker compose logs --tail 200 db
docker compose exec api alembic current
```
Verify the API's database hostname is the Compose service name, not `localhost` from inside the API container. Verify credentials match the local environment.

### Backend tests fail
- Re-run the failing test alone to isolate the cause.
- Confirm migrations and environment variables are correct.
- Do not weaken assertions or replace PostgreSQL integration coverage with mocks just to get a green run.
- Report the exact command, first meaningful traceback, commit, and environment.

### Frontend dependency or lockfile mismatch
- Use the package manager and lockfile committed by the repo.
- Do not mix npm and pnpm lockfiles without Developer A approval.
- Do not use `--force` audit fixes.

### API works locally but not from the browser
- Check the API base URL and CORS/origin configuration.
- Inspect browser network and API logs.
- For cookie auth, verify credentials mode, cookie attributes, allowed origin, and CSRF configuration.
- Do not solve auth/CORS issues by allowing all origins with credentials.

## 11. Before asking for help

Include:
1. operating system and shell;
2. `git rev-parse --short HEAD` and `git status --short`;
3. exact command run;
4. relevant logs with secrets redacted;
5. whether Docker and DB are healthy;
6. whether the failure reproduces on latest `main`.

Never share `.env`, access tokens, Google credentials, database passwords, session cookies, or raw secret values.
