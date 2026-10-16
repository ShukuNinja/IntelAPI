# API Intelligence Platform — Stage 2 Scaffold

This package carries forward the Stage 1 frontend and adds the initial FastAPI, PostgreSQL, Alembic, Docker Compose, and GitHub Actions foundation. It is not yet a working API testing engine.

## Full stack (Windows PowerShell)
1. Copy `.env.example` to `.env` and set a local PostgreSQL password.
2. Ensure Docker Desktop is running.
3. Run `docker compose up --build`.
4. Open frontend `http://localhost:5173`, API docs `http://localhost:8000/docs`, liveness `http://localhost:8000/health/live`, readiness `http://localhost:8000/health/ready`.

## Backend direct on Windows
```powershell
cd apps/api
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
# Start PostgreSQL first and set DATABASE_URL in apps/api/.env
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Frontend checks
```powershell
npm install --prefix apps/web
npm run typecheck --prefix apps/web
npm run lint --prefix apps/web
npm run build --prefix apps/web
```

## Backend checks (with the venv activated)
```powershell
cd apps/api
ruff check .
mypy app
pytest
```

## Implemented now
- `GET /health/live`: process liveness, independent of database.
- `GET /health/ready`: database connectivity check.
- `GET /api/v1/meta`: API metadata.
- Centralized settings, logging, SQLAlchemy engine/session, Alembic baseline, module responsibility notes, Docker Compose and CI workflow.

## Not implemented yet
Google sign-in, application sessions, domain tables, target HTTP execution/SSRF safeguards, OpenAPI import persistence, campaign worker, test generation, analysis, adaptive selection, findings persistence and reports. Do not represent these as implemented.

See `docs/` for the five approved design documents.
