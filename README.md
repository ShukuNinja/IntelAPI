# IntelAPI â€” AI-Powered Intelligent API Testing Platform

IntelAPI is an API development and testing workspace augmented with API understanding, evidence-driven analysis, and adaptive test generation.

## Product workflow

**Configure API â†’ Understand contract â†’ Generate tests â†’ Execute safely â†’ Validate responses â†’ Analyze evidence â†’ Select follow-up tests â†’ Report findings**

The ordinary API-client workflow must remain useful when no LLM provider is configured. AI output is untrusted input and must be validated. An unusual response is an observation, not automatically a confirmed defect.

## Project status

The repository contains an integrated backend foundation and intelligence modules, but it is **not yet a complete API-testing product**. Authentication and project endpoints, persistence models/migrations, and intelligence algorithms exist. Workspace CRUD endpoints, the shared secure outbound execution service, durable execution/history, public intelligence workflow endpoints, durable campaigns, evidence/report APIs, and complete frontend-to-backend integration remain to be implemented or verified.

Read [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) for the current evidence-based status and [`docs/M0_BASELINE_AUDIT.md`](docs/M0_BASELINE_AUDIT.md) for the baseline audit and identified gaps.

## Canonical documentation

- [`docs/SOURCE_OF_TRUTH.md`](docs/SOURCE_OF_TRUTH.md) â€” product goals, business rules, architecture, and accepted decisions.
- [`docs/api_contracts.md`](docs/api_contracts.md) â€” target HTTP API and shared contracts.
- [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md) â€” target relational schema and migration order.
- [`docs/IMPLEMENTATION_PLAN_AND_OWNERSHIP.md`](docs/IMPLEMENTATION_PLAN_AND_OWNERSHIP.md) â€” milestones, ownership, and workflow.
- [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) â€” observed implementation status and verification checklist.
- [`docs/LOCAL_RUNBOOK.md`](docs/LOCAL_RUNBOOK.md) â€” local setup and verification commands.
- [`docs/M0_BASELINE_AUDIT.md`](docs/M0_BASELINE_AUDIT.md) â€” audit evidence for the current source snapshot.

A documented endpoint, table, module, or feature is not proof that it is implemented. Status claims must be backed by source inspection, tests, or a demonstrated user-visible flow.

## Security baseline

Never commit `.env`, OAuth client secrets, LLM API keys, access tokens, real user data, database dumps, or local database files. All outbound target requests, including URL-based specification imports, must pass through the approved security boundary. Never execute generated candidates without validation and explicit execution.

## Contribution baseline

- Do not push feature work directly to `main`.
- Use scoped feature branches and pull requests.
- Keep changes within the ownership recorded in `docs/IMPLEMENTATION_PLAN_AND_OWNERSHIP.md`.
- Run the relevant backend, frontend, migration, and security tests before requesting review.
