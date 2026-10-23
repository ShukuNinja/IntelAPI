# Start IntelAPI locally (Windows)

## Prerequisites

- Docker Desktop running with the Linux container engine
- Git (for a fresh clone)

## First-time setup

Open PowerShell and run:

```powershell
git clone https://github.com/ShukuNinja/IntelAPI.git
cd IntelAPI
git switch final-version
Copy-Item .env.example .env
notepad .env
```

In `.env`, change `POSTGRES_PASSWORD` from the example value to a local password. Keep `ENVIRONMENT_ENCRYPTION_KEY` stable if you save encrypted environment secrets. To generate one, run:

```powershell
docker compose run --rm api python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Paste the generated value into `.env`. Keep `.env` private; never commit it.

## Start the app

From the repository root:

```powershell
docker compose up --build -d
docker compose ps
docker compose exec api alembic upgrade head
```

Open the web app at [http://localhost:5173](http://localhost:5173). API health endpoints are [http://localhost:8000/health/live](http://localhost:8000/health/live) and [http://localhost:8000/health/ready](http://localhost:8000/health/ready). The `worker` service must be running for campaigns to progress.

## Demo flow

1. In **API Explorer**, create a project and import or paste an OpenAPI/Swagger document.
2. Review the discovered operations and generate a candidate report.
3. In **API Workspace**, send a request to a reachable API, inspect the response, and optionally save the request/environment.
4. In **Campaigns**, choose a project/report and a reachable target, then queue a small campaign. State-changing methods require confirmation.

Only use targets you are authorized to test. For localhost targets, confirm `ALLOW_LOCAL_TARGETS=true` in `.env`.

## Stop and troubleshoot

```powershell
docker compose logs --tail 100 api
docker compose logs --tail 100 worker
docker compose logs --tail 100 web
docker compose down
```

If Docker reports that its engine is unavailable, start Docker Desktop and wait for the Linux engine to become ready, then retry `docker compose up --build -d`. Avoid `docker compose down -v`: it deletes the local PostgreSQL data volume.
