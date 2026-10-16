# DEVELOPMENT_WORKFLOW.md

**Project:** API Intelligence Platform  
**Status:** Proposed team workflow  
**Version:** 1.0  
**Last updated:** 2026-10-16  
**Audience:** Both developers, reviewers, and any coding agents working on the repository

> This document defines how both developers plan, implement, test, review, and integrate work. It is not a personal checklist for one developer. Neither developer should independently redefine shared contracts or merge incompatible implementations.

## 1. Purpose and Authority

Use this document together with:

1. `SOURCE_OF_TRUTH.md` — approved product requirements and constraints.
2. `TECHNICAL_DESIGN.md` — architecture, module boundaries, and runtime behavior.
3. `API_CONTRACT.md` — frontend/backend API interfaces.
4. `DATABASE_DESIGN.md` — persistence model, constraints, and migration rules.

If documents disagree, stop and report the conflict. Do not silently choose whichever rule is easiest to implement. The integration lead records the resolution in the appropriate source document and updates dependent documents before implementation continues.

This workflow establishes collaboration mechanics; it does not override the technical design or authorize scope expansion.

## 2. Team Roles

### Developer A — Integration Lead and Frontend Owner

Developer A owns the end-to-end integration process and initially implements the frontend. Developer A also owns the shared backend foundations and a major core feature area.

Responsibilities:

- Maintain the approved architecture and decision log.
- Build the frontend shell, routing, design system, shared UI primitives, and the six primary product destinations.
- Implement typed frontend service interfaces against `API_CONTRACT.md`; use explicit mock services until the real backend is ready.
- Own or coordinate shared contracts, application configuration, authentication foundations, database setup, migration integration, and the shared request-execution foundation as assigned in the technical design.
- Define integration order and identify cross-module dependencies.
- Review changes that affect shared schemas, database migrations, configuration, security boundaries, module exports, or architecture.
- Integrate branches, resolve cross-module failures, maintain CI health, and coordinate end-to-end acceptance testing.
- Ensure the final product works as one system, not merely as independently passing modules.

Developer A does not have to implement every backend feature. Integration ownership means coordinating and validating integration, not absorbing all implementation work.

### Developer B — Testing-Intelligence Feature Owner

Developer B owns the assigned testing-intelligence modules and their tests, documentation, and integration readiness.

Responsibilities:

- Read and follow the approved source-of-truth, technical design, API contract, and database design before implementing a module.
- Implement assigned bounded modules, initially focused on test-candidate generation, deterministic analysis/assertions, interestingness scoring, adaptive follow-up selection, and campaign/report integration as divided in the task plan.
- Keep module logic separate from FastAPI route handlers, database plumbing, and target HTTP execution.
- Use the approved public interfaces and schemas; do not create competing versions of shared types or duplicate core execution logic.
- Add unit and integration tests for success, invalid input, boundary conditions, and failure paths.
- Document module inputs, outputs, assumptions, configuration, and known limitations.
- Submit focused pull requests and respond to review feedback.
- Report missing or contradictory contracts early, with a proposed change, rather than silently inventing behavior.

Developer B may contribute to other modules when explicitly agreed, but should not modify shared foundations or files owned by Developer A without coordination and review.

### Shared responsibilities

Both developers must:

- Understand the complete product workflow and the interfaces between their modules.
- Review the contract before coding against a dependency.
- Keep commits focused and provide meaningful tests.
- Review one another's pull requests where practical.
- Communicate blockers and integration risks early.
- Avoid committing secrets, local environment files, generated build artifacts, or unreviewed schema changes.
- Validate the final user workflow together before declaring the MVP complete.

## 3. Ownership Matrix

Ownership indicates the default implementer, not permission to change shared interfaces unilaterally.

| Area | Default owner | Required coordination |
|---|---|---|
| Product scope and architecture decisions | Developer A | Both developers review material scope changes |
| Source-of-truth and cross-document consistency | Developer A | Developer B flags gaps and proposes amendments |
| Frontend shell, routing, design tokens, shared components | Developer A | Developer B supplies UI needs and reviews relevant flows |
| Frontend feature pages and typed API client | Developer A initially | Both agree on any frontend work reassignment |
| API contract and shared Pydantic schemas | Developer A coordinates | Developer B reviews and implements against the accepted contract |
| FastAPI scaffold, settings, error handling, shared utilities | Developer A | Shared changes require review |
| Authentication and authorization foundations | Developer A | Developer B uses approved auth/ownership dependencies; does not bypass them |
| PostgreSQL, SQLAlchemy base, Alembic integration | Developer A | Both agree on model changes and migration order |
| Projects and core saved-resource foundations | Developer A, unless reassigned | Shared API and DB contracts must remain aligned |
| Shared outbound HTTP execution and SSRF controls | Developer A | No second HTTP execution implementation; Developer B calls the approved service |
| API/spec understanding and knowledge representation | Split by task plan | Agree on schemas and provenance before parallel work |
| Test candidate generation | Developer B | Uses approved API understanding and LLM adapter interfaces |
| Deterministic assertions and response analysis | Developer B | Must distinguish contract violations from observations and hypotheses |
| Interestingness scoring and adaptive follow-up policy | Developer B | Scoring inputs and outputs must be documented and testable |
| Campaign domain logic / worker integration | Shared boundary | Developer A owns runtime/worker foundations; Developer B owns agreed testing loop logic |
| Evidence and reporting | Developer B for analysis/report logic; Developer A for persistence/integration foundations | Agree on persistence schemas and evidence provenance |
| Docker Compose, CI, branch protection, release integration | Developer A coordinates | Both fix failures caused by their changes |
| Module-specific tests and docs | Module owner | Both contribute to end-to-end tests |
| Final acceptance and demo readiness | Both | Developer A coordinates the release checklist |

If the actual team names are added later, use role labels in this document until then to avoid ambiguity.

## 4. Development Stages and Parallelism

### Stage 0 — Shared design baseline

**Both developers:**

1. Read the four governing documents.
2. Review the MVP scope, architecture, API contract, database design, and security constraints.
3. Record ambiguities as concrete questions with a suggested resolution.
4. Agree on the first set of tasks and their acceptance criteria.

**Developer A:** establishes the repository, baseline configuration, branch rules, and integration plan.  
**Developer B:** reviews the intelligence-module boundaries and prepares a module-level implementation plan and test cases.

Do not start independent backend implementations while key interfaces are still contradictory.

### Stage 1 — Frontend-first implementation with contract alignment

**Developer A leads frontend implementation:**

- Application shell, route structure, navigation, design tokens, and reusable components.
- Overview, API Workspace, Health Checks, API Explorer, Test Campaigns, and Findings & Evidence routes.
- Typed service layer and explicit mock fixtures that conform to `API_CONTRACT.md`.
- Loading, empty, error, and success states.

**Developer B works in parallel on backend preparation:**

- Review the API contract and database design for gaps affecting the intelligence modules.
- Specify candidate-generation, analysis, scoring, and adaptive-selection input/output examples.
- Create test matrices and deterministic fixtures for the owned modules.
- Prototype isolated pure-domain logic only where its interfaces are stable; avoid committing incompatible API/DB scaffolding.

Both developers must keep mock data clearly separated from real service calls. The frontend must not imply that a mocked action has executed a real request or campaign.

### Stage 2 — Repository and backend foundation

**Developer A leads:**

- Backend package layout, settings, logging, error envelope, database session, SQLAlchemy base, Alembic, health endpoint, and Docker Compose integration.
- Shared Pydantic schemas and API route/service conventions.
- Authentication and server-side resource ownership foundations.
- CI jobs and baseline tests.

**Developer B:**

- Implements owned domain modules behind the agreed service interfaces.
- Adds unit tests with fake repositories/provider adapters where suitable.
- Avoids changing shared models or migrations without an explicit proposal and review.

The team should make the smallest integrated vertical slice work before expanding: app starts, database connects, migration applies, health endpoint responds, authentication/ownership checks work, and CI passes.

### Stage 3 — Core API-client vertical slice

Implement in an integration-friendly order:

1. Authentication and project ownership.
2. Project and saved-resource persistence.
3. Request configuration and shared outbound execution.
4. Response capture and request history/evidence.
5. Deterministic assertions and health checks.
6. OpenAPI import and API operation representation.
7. Test candidate generation and validation.
8. Campaign execution, analysis, adaptive follow-ups, and reports.

The exact order can change when dependencies justify it, but each slice must leave the default branch in a working, tested state. Do not build the entire intelligence pipeline against fake interfaces and attempt one large integration at the end.

### Stage 4 — Integration, hardening, and release

**Both developers:**

- Run unit, integration, and end-to-end tests.
- Verify failure paths and resource limits, not only successful demonstrations.
- Verify the app remains useful without LLM credentials.
- Confirm secrets are not returned to the frontend or written to logs.
- Test campaign interruption/recovery and unsafe URL rejection.
- Resolve CI failures before adding more features.
- Update known limitations and demo instructions.

**Developer A coordinates** the final checklist, but both developers are responsible for bugs in their own modules.

## 5. Git and Branching Workflow

Use a short-lived feature-branch workflow. The default branch must remain releasable.

### Branch naming

Use descriptive prefixes, for example:

- `feat/frontend-api-workspace`
- `feat/auth-session`
- `feat/test-generation`
- `feat/adaptive-scoring`
- `fix/response-size-limit`
- `test/campaign-recovery`
- `docs/api-contract-update`
- `chore/ci-backend`

### Rules

1. Never commit directly to the protected/default branch for ordinary feature work.
2. Create a branch from the latest default branch.
3. Keep a pull request focused on one coherent feature or fix.
4. Sync with the default branch before final review; resolve conflicts locally and rerun affected tests.
5. Do not force-push shared branches. If a feature branch is private and history rewriting is necessary, coordinate first.
6. Do not merge a pull request with failing required checks or unresolved high-impact review comments.
7. Delete merged branches when appropriate.
8. Do not commit `.env`, OAuth client secrets, LLM keys, access tokens, real user data, or local database files. Keep `.env.example` populated only with safe placeholders.

### Commit messages

Prefer concise imperative or Conventional Commit-style messages, such as:

- `feat(api): add request execution service`
- `test(adaptive): cover follow-up selection boundaries`
- `fix(auth): enforce project ownership`
- `docs(contract): define campaign status transitions`

A commit should represent a coherent change. Avoid unrelated formatting, refactors, and features in one commit.

## 6. Contract-First Change Procedure

If a task requires changing an API schema, database model, event shape, shared type, or module boundary:

1. Open a small proposal in the pull request description or a decision note.
2. State the problem, proposed change, affected modules, migration implications, and backward-compatibility impact.
3. Update the relevant source document(s) first or in the same reviewed change.
4. Update Pydantic schemas, TypeScript types, persistence mappings, and tests consistently.
5. Include migration and compatibility handling where persisted data or deployed clients require it.
6. Ask the other developer to review the cross-module impact.
7. Merge only after dependent code and tests agree with the new contract.

Do not let the frontend, backend, and database each define their own interpretation of the same field. The API contract is the boundary source for external requests and responses; the database design is the source for persistence constraints.

## 7. Pull Request Procedure

Every pull request should include:

- **Purpose:** what behavior changes and why.
- **Scope:** modules and files affected.
- **Contract impact:** none, or links to updated contract/design sections.
- **Tests:** commands run and meaningful outcomes.
- **Security impact:** outbound requests, secrets, auth, ownership, parsing, or resource limits affected.
- **UI evidence:** screenshots or a short recording for material frontend changes, when practical.
- **Known limitations:** remaining gaps, temporary mocks, and follow-up tasks.

### Review checklist

The reviewer checks:

- The implementation matches approved requirements and module boundaries.
- External inputs are validated and errors are predictable.
- Project/resource ownership is enforced on the server.
- Target API calls go through the shared safe execution service.
- LLM output is treated as untrusted and validated before execution.
- Secrets and sensitive response data are not leaked.
- Tests cover meaningful success, error, and boundary cases.
- No undocumented contract or migration change is hidden in the implementation.
- Documentation and examples match actual behavior.

The author is responsible for addressing review comments and rerunning affected tests. The reviewer is responsible for explaining blocking feedback clearly.

## 8. Testing Workflow

Run the narrowest useful test set during development, then the relevant broader checks before opening or merging a pull request.

### Frontend owner checklist

- Lint and TypeScript type-check.
- Component and service tests for changed behavior.
- Verify loading, empty, error, and success states.
- Confirm request/response schemas match the API contract.
- Verify mock services are not used silently in production configuration.
- Run production build.

### Backend/module owner checklist

- Format/lint and static type checks according to repository configuration.
- Unit tests for domain logic with deterministic fixtures.
- API tests for status codes, response envelopes, and validation failures.
- Database integration tests for persistence, constraints, ownership, and migrations where affected.
- Mock LLM providers in normal CI; live-provider tests are opt-in.
- Verify timeout, response-size, retry, and failure behavior for outbound operations where applicable.

### Integration checklist

- Run the required CI workflow.
- Apply migrations to a clean database and verify the upgrade path.
- Run at least one end-to-end path through the actual frontend and backend.
- Confirm the product's basic API-client path works with no LLM configuration.
- Confirm campaign state and evidence survive worker/API restarts as designed.

Do not mark tests as passed unless they were actually executed. If an environment limitation prevents a test, report it explicitly.

## 9. Shared Files and Collision Prevention

The following areas require coordination before edits by both developers:

- `SOURCE_OF_TRUTH.md`, `TECHNICAL_DESIGN.md`, `API_CONTRACT.md`, `DATABASE_DESIGN.md`, and this workflow document.
- Root workspace manifests and lockfiles.
- CI workflows, Docker Compose, Dockerfiles, and shared environment examples.
- Central settings, logging, error handling, authentication dependencies, and database setup.
- Shared Pydantic schemas, TypeScript API types, SQLAlchemy base/model registration, and Alembic migrations.
- Common execution-service interfaces and security policy.

Before changing a shared file, announce the intended change and check whether the other developer has an active branch touching it. If simultaneous work is unavoidable, agree on the edit order and integrate immediately rather than letting both branches diverge.

Never resolve a migration conflict by deleting another developer's migration or rewriting a shared migration that may already have been applied. Coordinate a safe migration sequence.

## 10. Coding-Agent Workflow

Coding agents may accelerate implementation, but they do not own architecture decisions.

Before assigning an agent a task, provide:

- The relevant sections of the governing documents.
- Exact files/directories it may modify.
- Public interfaces it must preserve.
- Required tests and acceptance criteria.
- Explicit non-goals and files it must not change.

Require the agent to report:

1. Files changed.
2. Design choices made and assumptions used.
3. Tests actually executed and results.
4. Tests not executed and why.
5. Security or integration risks.
6. Any contract gap that needs a human decision.

Do not allow two agents or developers to edit the same files concurrently without coordination. Review generated code as untrusted code: inspect the diff, validate dependencies, run tests, and verify security-sensitive behavior before merging.

## 11. Communication and Blocker Handling

Use a lightweight shared task board or issue list. Every task should have an owner, status, dependencies, acceptance criteria, and links to relevant contracts.

Suggested statuses:

`Backlog → Ready → In Progress → In Review → Integration → Done`

Use `Blocked` when a contract, dependency, environment, or decision prevents progress.

When blocked, report:

- What is blocked.
- The exact dependency or missing decision.
- What has already been tried.
- The smallest proposed resolution.
- Whether another independent task can proceed meanwhile.

Raise integration risks as soon as they are discovered, not at the end of a feature. If the two developers disagree on architecture or scope, pause the affected change, compare it against the governing documents, and record a decision before proceeding.

A short daily sync is sufficient: completed work, next task, blocker, and likely cross-module conflict. Keep it factual and focused on dependencies.

## 12. Definition of Done

A task is complete only when all applicable conditions are met:

- Acceptance criteria are satisfied.
- The implementation follows the approved design and contracts.
- Required tests were executed and passed, or any blocked tests are explicitly reported and accepted.
- Error and boundary behavior is handled.
- Authorization, secret handling, outbound safety, and resource limits are preserved.
- No accidental demo/mock behavior is presented as a real operation.
- The pull request has been reviewed and required CI checks pass.
- Documentation, examples, and migrations are updated where applicable.
- The code is integrated with its dependent modules or the remaining integration dependency is explicit.

A module passing unit tests is not sufficient if its public interface does not integrate with the rest of the application.

## 13. Release and Demo Checklist

Before tagging a milestone or demonstrating the MVP, both developers verify:

- A clean checkout can be configured using documented steps and safe environment placeholders.
- Docker Compose starts the required services and migrations apply successfully.
- Authentication and server-side ownership checks work.
- The frontend's six primary destinations load and handle API errors coherently.
- Manual API execution uses the shared safe execution path.
- Response details and evidence reflect actual execution results.
- Health checks distinguish reachability, HTTP status, and assertion outcomes.
- Campaigns enforce request/iteration/time limits and persist their state.
- AI-generated candidates are validated before execution; provider failure does not fabricate results.
- The basic API-client workflow works without LLM credentials.
- CI passes, known limitations are documented, and no secrets are present in the repository.

## 14. Working Principle

**Parallelize implementation, not decisions about shared interfaces.** Developer A coordinates foundations and integration; Developer B owns the agreed intelligence modules. Both developers are responsible for contract alignment, tests, security, review, and the integrated product outcome.
