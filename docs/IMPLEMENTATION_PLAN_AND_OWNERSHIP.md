# IntelAPI — Implementation Plan and Rigid Ownership Contract

**Version:** 1.0
**Baseline date:** 2026-10-16
**Owners:** Developer A (integration lead) and Developer B (intelligence lead)

This document is normative for work assignment. The product and technical contracts are in `SOURCE_OF_TRUTH.md`. A task does not grant ownership of a file merely because a developer can edit it.

## 1. Ownership principles

1. One primary owner per file/module. The owner implements, tests, and maintains it.
2. The other developer may review and propose changes but must not independently modify a protected file/module.
3. Shared interfaces are agreed before parallel implementation. Developer A owns API/DB contract coordination and final integration.
4. Any cross-owner change requires a PR with explicit approval from the owner and Developer A.
5. Do not create empty placeholder files for the entire manifest. Add files when a milestone has a concrete implementation and tests.
6. Do not rename/reorganize protected modules or alter public contracts as incidental cleanup.
7. No direct pushes to `main`. All work happens on feature branches from latest `main`, through PR, CI, review, and squash merge.
8. Never commit `.env`, secrets, tokens, private test data, or local database volumes.
9. If work reveals a contract gap, stop at the interface boundary, write a proposal, and obtain approval before changing shared DTOs/schema.
10. The role split is about code and decisions, not only feature labels. Developer A has final authority over integration, security boundaries, API schema, database migrations, and releases.

## 2. Developer responsibilities

### Developer A — integration lead and platform owner

Accountable for:
- product/API/database contract coordination and this canonical documentation set;
- auth/session security and project ownership enforcement;
- SQLAlchemy base/session wiring, ORM registry, Alembic revisions and migration order;
- projects, saved-resource persistence, workspace routes and persistence;
- secure shared outbound execution service and its threat model;
- durable campaign/job persistence, worker lifecycle, leases/recovery, cancellation/budgets;
- health-check persistence and API integration;
- findings/evidence persistence, report/overview aggregation;
- frontend shell, API client/service integration, auth/project/workspace flows, generated API types;
- Docker Compose, CI, migration integration, end-to-end tests, integration fixes, release readiness.

Developer A may delegate implementation of domain algorithms but retains ownership of their public contracts, persistence boundaries, security integration, and merge approval.

### Developer B — API intelligence and test-analysis owner

Accountable for:
- OpenAPI parsing, normalization, operation extraction and schema-derived facts;
- knowledge fact extraction and provenance;
- provider-independent LLM interface and provider adapter;
- deterministic candidate generation, optional LLM-assisted generation, validation and deduplication;
- deterministic assertion evaluation and schema comparison;
- finding classification based on evidence;
- adaptive scoring, follow-up selection and rationale;
- intelligence-domain unit tests and integration adapters into campaign orchestration;
- candidate preview output semantics and test candidate quality.

Developer B must not change public API schemas, ORM models, Alembic migrations, auth/session, project ownership, outbound transport/security, campaign job/lease/state persistence, frontend shared services, Docker/CI, or protected files without an approved PR from Developer A.

## 3. Protected ownership matrix

`A` = primary owner; `B` = primary owner; `A→review` means B may propose but A must approve and perform/coordinate the change. Shared DTOs are agreed jointly; A is contract owner.

| Module / path | Owner | Protection rule |
|---|---|---|
| `docs/SOURCE_OF_TRUTH.md` | A | B may propose; A updates canonical decisions |
| `docs/IMPLEMENTATION_PLAN_AND_OWNERSHIP.md` | A | Ownership changes require explicit mutual agreement |
| `docs/IMPLEMENTATION_STATUS.md` | A | Both supply evidence; A publishes verified status |
| `docs/LOCAL_RUNBOOK.md` | A | B can report setup failures; A merges normative changes |
| `apps/api/app/core/config.py` | A | Security/config changes need A review |
| `apps/api/app/core/errors.py` | A | Shared error contract |
| `apps/api/app/core/logging.py` | A | Secret-safe logging |
| `apps/api/app/core/security.py` | A | Auth/CSRF/security primitives |
| `apps/api/app/core/pagination.py` | A | Shared API contract |
| `apps/api/app/db/base.py`, `session.py`, `models.py` | A | DB wiring and Alembic model registration protected |
| `apps/api/app/auth/**` | A | Protected identity/session/security domain |
| `apps/api/app/projects/**` | A | Ownership/archive/transactions |
| `apps/api/app/workspace/collections/**` | A | Saved-resource persistence |
| `apps/api/app/workspace/requests/**` | A | Request persistence and execution integration |
| `apps/api/app/workspace/environments/**` | A | Secret encryption/resolution |
| `apps/api/app/execution/**` | A | **Security-critical; B must not directly edit** |
| `apps/api/app/history/**` | A | Execution history/persistence |
| `apps/api/app/api_understanding/**` | B | A approves public schema and safe import integration |
| `apps/api/app/knowledge/**` | B | A approves persistence/model/migration changes |
| `apps/api/app/test_generation/**` | B | Candidate algorithms and validation |
| `apps/api/app/analysis/**` | B | Assertions, schema comparison, classification |
| `apps/api/app/adaptive/**` | B | Scoring/selection/rationale |
| `apps/api/app/integrations/llm/**` | B | Provider-neutral interface and adapters; secrets/config owned by A |
| `apps/api/app/campaigns/router.py`, `schemas.py` | A | Public API/state contract protected |
| `apps/api/app/campaigns/repository.py`, `models.py`, `job_claim.py`, `worker.py`, `state_machine.py`, `orchestrator.py` | A | Durable job, lease, recovery, cancellation and state persistence protected |
| `apps/api/app/campaigns/service.py` | A | B may implement an agreed intelligence hook in a separate B-owned module; A integrates |
| `apps/api/app/health_checks/router.py`, `schemas.py`, `service.py`, `repository.py`, `models.py` | A | Persistence and routes |
| `apps/api/app/health_checks/assertions.py` | B | Fixed five assertion semantics; A approves integration contract |
| `apps/api/app/evidence/**` | A | Persistence, redaction, provenance links |
| `apps/api/app/findings/**` | A | API, persistence and user-managed triage fields; B owns classifier in `analysis/` |
| `apps/api/app/reports/**`, `overview/**` | A | Aggregate read APIs |
| `apps/api/app/main.py`, `api.py` | A | Router registration, middleware, startup/lifespan |
| `apps/api/alembic/**` | A | Only A authors/merges migrations |
| `apps/api/tests/**` | Split by module owner | A owns integration/security/DB tests; B owns intelligence unit tests; cross-domain test requires coordination |
| `apps/web/src/app/**` | A | Routing/providers/protected routes |
| `apps/web/src/services/api-client.ts`, `generated/**` | A | Generated file is never hand-edited |
| `apps/web/src/services/**` | A | Shared API integration; B supplies schema needs, not direct changes |
| `apps/web/src/features/**` | A | All frontend feature implementation and integration in current two-person split |
| `apps/web/src/components/**`, `lib/**`, `styles/**` | A | Shared UI/client primitives |
| `apps/web/src/mocks/**` | A | Temporary fixture/demo cleanup |
| `packages/contracts/**` | A (contract owner) | B proposes changes; both approve DTO impact |
| `scripts/export_openapi.py`, `scripts/generate_api_types.py` | A | CI/type generation pipeline |
| `.github/workflows/**`, `Dockerfile*`, `compose*.yml`, CI config | A | Protected deployment/quality gate |
| `pyproject.toml`, package manifests/lockfiles, workspace config | A | B must not change dependencies without approval |
| `README.md`, `.env.example` | A | Run instructions/config contract; no secrets |

**Existing paths:** reuse the existing scaffold paths when possible. This matrix defines intended ownership for the modules as they are introduced; it does not claim every listed file already exists.

## 4. Shared contracts that must be agreed before parallel PRs

Developer A owns the HTTP and persistence boundary. Developer B owns intelligence-domain implementation behind that boundary. Agree these types before implementation:
- `NormalizedOperation`
- `TestCandidate`
- `ExecutionResult`
- `AssertionResult`
- `FindingRead`
- `EvidenceReferenceRead`
- `CampaignRead`

Rules:
- HTTP DTOs are Pydantic schemas; frontend types are generated from FastAPI OpenAPI.
- Domain objects and ORM models are not reused as HTTP DTOs.
- B can propose a new field, but must state purpose, source/provenance, optionality, compatibility, and tests.
- A accepts/rejects the change and updates the source of truth if the contract changes.
- Never allow B's intelligence implementation to call HTTPX directly or bypass the shared execution service.

## 5. Git and PR permissions

### Branch rules
- Branch from current `main`; use descriptive branch names such as `feat/openapi-normalizer`, `feat/project-persistence`, `test/target-policy`.
- No direct commits to `main`; no force-push to shared branches.
- Keep PRs scoped to one module/contract.
- Do not include unrelated formatting, lockfile churn, or mass refactors.

### Required PR content
Every PR must state:
1. user-visible capability or invariant implemented;
2. owner and files changed;
3. contract changes (or “none”);
4. migration impact (or “none”);
5. security implications (especially outbound requests/secrets);
6. tests added and exact commands/results;
7. known limitations and status changes.

### Review/merge rules
- Developer A reviews every PR touching API contracts, DB, auth, outbound execution, campaigns/jobs, frontend integration, shared config, CI, dependencies, or deployment.
- Developer B reviews intelligence algorithm changes and candidate/analysis contract use.
- Cross-owner PR requires both the file owner and Developer A; for B-owned intelligence logic, A review is still required before merging into a shared integration branch.
- CI green is required. If a check cannot run locally, report why and rely on CI; do not claim it passed.
- Squash merge after approval. Update status only after merge and verification.

## 6. Implementation sequence and gates

Do not start by generating every planned file. Implement complete vertical slices and add only the files required.

### Phase 0 — Contract freeze and repo hygiene
**A leads; B reviews.**
- Commit the four-document canonical set.
- Inspect current Alembic graph, repo paths, Compose, environment variables, and CI.
- Reconcile liveness contract with current `{"status":"alive"}` behavior.
- Agree shared DTOs and create short interface examples/tests.
- Add/verify branch protection and secret exclusion.
**Exit gate:** docs committed; clean baseline; current tests/Compose commands recorded; no unresolved ownership conflict.

### Phase 1 — Persistence foundation and intelligence harness
**A:** users/session/project models, initial real migrations, project ownership dependency, project CRUD/archive.
**B:** OpenAPI parser/normalizer tests and deterministic fixtures using agreed DTOs; no dependency on unmerged DB migrations.
**Exit gate:** migration from empty PostgreSQL; ownership-isolation tests; parser tests pass.

### Phase 2 — Workspace and safe execution / API understanding
**A:** collections, requests, environments, secret encryption, shared execution transport/policy/capture/redaction/budgets, history persistence.
**B:** specification parsing/normalization/operation extraction, knowledge facts, deterministic candidate generator, validation/deduplication, LLM interface behind adapter.
**Exit gate:** request execution saved to history; SSRF tests pass; file import and safe URL import pass; preview is non-persisting; deterministic candidates work without LLM credentials.

### Phase 3 — Assertions, health checks, findings/evidence
**A:** health-check persistence/routes/runs; evidence/finding persistence and APIs; user-managed finding triage fields.
**B:** assertion evaluation/schema comparison/classification algorithms; five health assertion semantics and tests; evidence/provenance payload proposal.
**Exit gate:** fixed assertion types work; findings link to reproducible executions/evidence; no unsupported automatic defect classification.

### Phase 4 — Durable campaigns and adaptive loop
**A:** campaign/job/event schema and migrations; atomic campaign/job/event creation; worker, claim/lease/recovery, cancellation, budgets, persistence, report endpoints.
**B:** adaptive scoring, follow-up selection/rationale; candidate generation/classification hooks; intelligence integration through agreed interfaces.
**Exit gate:** campaign survives API/worker restart; no blind retry after uncertain execution; terminal cancellation idempotent; budget exhaustion recorded; partial report works when evidence exists.

### Phase 5 — Frontend and complete workflows
**A:** auth/session UX, project shell/overview, workspace, explorer preview, health checks, campaigns, findings/evidence, services and generated types.
**B:** supports API contract review and intelligence UI payloads; does not directly edit frontend files without explicit assignment.
**Exit gate:** UI calls real endpoints for completed features; no demo fixtures masquerading as persisted data; type generation drift check passes.

### Phase 6 — Hardening and release candidate
**A:** Compose/CI, E2E, migrations, docs, security review, integration fixes.
**B:** intelligence quality/regression tests and end-to-end result interpretation review.
**Exit gate:** full test suite and migration tests pass; four E2E flows pass; secrets are not leaked; README/runbook accurate; status marks only verified behavior complete.

## 7. Module implementation checklist

### Developer A checklist
- [ ] Auth: Google token verification, stable `sub`, hashed opaque sessions, expiry/revocation/logout, cookie/CSRF/origin rules.
- [ ] Projects: CRUD/archive, owner isolation, pagination/errors.
- [ ] Workspace: collections, requests, environments, encrypted secret values, resolver.
- [ ] Execution: target policy, DNS/redirect validation, HTTPX transport, timeout/budget/size caps, redaction, immutable snapshot.
- [ ] History: durable execution records and detail endpoint.
- [ ] API wiring: routers, app lifespan, structured errors, health/readiness.
- [ ] DB: ORM registry, migrations, constraints/indexes, integration fixtures.
- [ ] Health checks: saved definitions/runs and fixed assertion integration.
- [ ] Campaigns: state machine, jobs, leases, worker, events, cancellation, recovery, budgets.
- [ ] Findings/evidence/report/overview: durable records, provenance, aggregate APIs.
- [ ] Frontend: services/pages, auth/project flows, generated types, loading/error/empty states.
- [ ] CI/Compose/E2E: backend, frontend, DB migration and type drift gates.

### Developer B checklist
- [ ] OpenAPI parser: validate versions/size, parse JSON/YAML safely, reject unsupported/invalid documents clearly.
- [ ] Normalizer: deterministic normalized operation IDs, parameters, request bodies, responses, schema refs.
- [ ] Operation extraction: operations and schema relationships with source provenance.
- [ ] Knowledge: facts tagged `DECLARED`, `EXTRACTED`, `OBSERVED`, `INFERRED`.
- [ ] Candidate generation: positive, negative, boundary, schema, workflow cases; deterministic default.
- [ ] Candidate validation and deduplication; bounded payloads and stable candidate IDs.
- [ ] LLM adapter: provider-independent interface, bounded prompts/output, schema validation, safe fallback.
- [ ] Assertions: status, latency, JSON path/value, response header, response schema.
- [ ] Analysis: schema comparison, evidence-based classification, confidence/rationale.
- [ ] Adaptive selection: scoring, diversity, budgets, explainable next-test rationale.
- [ ] Regression fixtures/tests for malformed specs, edge cases, duplicate candidates, unsupported schemas, ambiguous findings.

## 8. Definition of done

A feature is complete only when all applicable criteria hold:
- user story and API contract are implemented;
- authorization/ownership is enforced server-side;
- persistence and migration are correct where needed;
- deterministic tests cover success, failure, invalid input, and security boundaries;
- frontend has loading, empty, error, and success states if UI is involved;
- no secrets or unbounded payloads are logged/stored;
- docs/status updated with actual verification;
- CI passes and PR is reviewed/merged;
- feature is tested through the user-facing workflow, not just its isolated helper.

## 9. Prohibited shortcuts

- No direct writes to `main`.
- No ad-hoc schema edits or `create_all()` in place of migrations.
- No duplicate outbound HTTP clients for feature modules.
- No LLM-required baseline behavior.
- No public API/schema/migration edits by B without approval.
- No frontend fixtures presented as real persisted backend data.
- No claiming “exactly once” campaign execution.
- No retry after an ambiguous post-crash send.
- No deleting or rewriting history when archiving projects.
- No marking planned files/features as implemented.
