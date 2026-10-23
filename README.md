# IntelAPI — AI-Powered Intelligent API Testing Platform

IntelAPI is an API development and testing workspace augmented with API understanding, evidence-driven analysis, and adaptive test generation.

## Product workflow

**Configure API → Understand contract → Generate tests → Execute safely → Validate responses → Analyze evidence → Select follow-up tests → Report findings**

The ordinary API-client workflow must remain useful when no LLM provider is configured. AI output is untrusted input and must be validated. An unusual response is an observation, not automatically a confirmed defect.

## Product destinations

1. Overview
2. API Workspace
3. Health Checks
4. API Explorer
5. Test Campaigns
6. Findings & Evidence

Supporting destinations include Collections, Environments, Request History, and Login.

## Technology stack

- **Frontend:** React, Vite, TypeScript, React Router, Tailwind CSS, TanStack Query.
- **Backend:** Python, FastAPI, Pydantic, SQLAlchemy, Alembic.
- **Database:** PostgreSQL.
- **Outbound requests:** one shared HTTP execution service with SSRF protections, timeouts, execution budgets, and response-size limits.
- **Testing and CI:** pytest, frontend type/lint/build checks, and GitHub Actions.
- **Local development:** Docker Compose.

The backend is a modular monolith. Do not introduce microservices, Kubernetes, Redis/Celery, or separate vector/graph databases without an explicitly approved architecture decision.

## Project status

The current product has working vertical slices for OpenAPI/Swagger parsing, deterministic candidate previews and reports, persisted single-user projects/specifications, and bounded HTTP request execution with project history. PostgreSQL-backed authentication, discovery from remote docs URLs, saved request collections/environments, durable generation reports, candidate execution and assertions, feedback policies, readiness/drift analysis, and report exports remain incomplete. The Overview, campaigns, findings, and health destinations still contain demo-backed presentation and must not be read as evidence from live APIs.

The implementation-status document records what was verified, what remains missing, and the commands to re-check the working tree. Do not treat demo data, demo health indicators, or sample findings as observations about real target APIs.

## Canonical documentation

The following files are the authoritative development documentation. Read them before implementing or changing a feature.

- [`docs/SOURCE_OF_TRUTH.md`](docs/SOURCE_OF_TRUTH.md) — product goals, user needs, business rules, architecture, module boundaries, and accepted technical decisions.
- [`docs/api_contracts.md`](docs/api_contracts.md) — frozen target HTTP API, shared DTOs, error semantics, security rules, and contract-change process.
- [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md) — target relational schema, constraints, relationships, retention, and migration order.
- [`docs/IMPLEMENTATION_PLAN_AND_OWNERSHIP.md`](docs/IMPLEMENTATION_PLAN_AND_OWNERSHIP.md) — implementation phases, developer responsibilities, file/module ownership, branches, and integration rules.
- [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) — last verified implementation state, known gaps, and validation checklist.
- [`docs/LOCAL_RUNBOOK.md`](docs/LOCAL_RUNBOOK.md) — local setup, environment configuration, Docker Compose, migrations, tests, and troubleshooting.

**Authority rule:** these documents describe the accepted target unless a section explicitly labels itself as current implementation status. A documented endpoint, table, module, or feature is not proof that it has already been implemented. The FastAPI application and its generated OpenAPI schema must be reconciled with the frozen API contract as implementation proceeds.

## Quick start

Follow [`docs/LOCAL_RUNBOOK.md`](docs/LOCAL_RUNBOOK.md) for prerequisites, environment setup, startup, migrations, tests, shutdown, and troubleshooting. Do not assume that a frontend-only startup command runs the complete stack.

## Security and repository hygiene

Never commit `.env`, OAuth client secrets, LLM API keys, access tokens, real user data, database dumps, or local database files. Keep secrets in local environment configuration or the approved secret-management mechanism. Ensure `.env` remains ignored by Git.

All target API calls—including URL-based specification imports—must pass through the approved outbound-request security boundary. Do not bypass SSRF defenses, DNS/redirect revalidation, timeouts, or response limits.

## Contribution baseline

- Do not push feature work directly to `main`.
- Use scoped feature branches and pull requests.
- Keep changes within the file/module ownership recorded in `docs/IMPLEMENTATION_PLAN_AND_OWNERSHIP.md`.
- Run the relevant backend, frontend, migration, and security tests before requesting review.
- Change shared API or database contracts only through the documented review process.
- Do not create placeholder files for future modules merely to match the planned file manifest; implement a module when its phase begins.
