# SOURCE_OF_TRUTH.md

**Project:** API Intelligence Platform  
**Document status:** Baseline approved; detailed technical design in progress  
**Version:** 1.0  
**Purpose:** Establish the authoritative product scope, architecture principles, engineering constraints, and collaboration rules for developers and coding agents.

---

## 1. Authority and Change Control

This document is the project's authoritative source for product and engineering decisions.

- All developers and coding agents MUST read this document and the relevant module instructions before making changes.
- A lower-level document may add detail but MUST NOT silently contradict this document.
- Record consequential architectural changes in `docs/decisions/` using a short Architecture Decision Record (ADR).
- If implementation requirements conflict with this document, stop and raise the conflict instead of inventing a new convention.
- Keep this document concise and stable. Put detailed component design in `TECHNICAL_DESIGN.md`, HTTP interfaces in `API_CONTRACT.md`, data structures in `DATABASE_DESIGN.md`, and workflow rules in `DEVELOPMENT_WORKFLOW.md`.

## 2. Product Vision

Build a practical API development and testing workspace with familiar API-client capabilities, augmented by semantic API understanding, evidence-driven analysis, and adaptive test generation.

The product is not intended to reproduce every feature of Postman. It must provide a useful core API-testing workflow and differentiate itself through response-driven adaptive testing.

### 2.1 Product objectives

1. Let users configure and execute HTTP requests and inspect responses.
2. Help users discover API endpoints and understand declared and observed API structures.
3. Validate responses using deterministic checks and available API contracts.
4. Generate and execute meaningful test cases.
5. Preserve execution evidence and distinguish observations from interpretations.
6. Use previous execution evidence to select targeted follow-up tests.
7. Present findings with supporting evidence, classification, confidence where applicable, and recommended next actions.

### 2.2 Product principles

- The ordinary API workspace MUST remain useful when no LLM provider is configured or available.
- AI-generated interpretations MUST NOT be presented as verified facts without supporting evidence.
- An unusual response is an observation, not automatically a defect.
- Declared contract, inferred hypothesis, and observed behavior MUST remain distinguishable.
- The product MUST NOT claim complete endpoint discovery for undocumented APIs based on a single request.
- The product MUST communicate limitations and execution failures explicitly.

## 3. Approved MVP Scope

### 3.1 Core API workspace

The planned MVP includes:

- HTTP methods: GET, POST, PUT, PATCH, DELETE, HEAD, and OPTIONS.
- URL/path parameters, query parameters, headers, request body, and authentication configuration.
- Sending requests and inspecting status, response time, response headers, body, and errors.
- Formatted JSON and raw response views.
- Basic deterministic assertions and response schema validation.
- Saved requests, collections, environments/variables, and request history at an agreed MVP depth.
- OpenAPI specification import and cURL import where feasible within the implementation plan.

Advanced features such as a complete Postman-compatible scripting runtime, every OAuth flow, team collaboration, and enterprise workspace management are not MVP requirements unless explicitly approved later.

### 3.2 Health checks and diagnostics

- Users can manually execute a configured endpoint check and rerun it.
- Results distinguish transport/reachability failures, timeouts, HTTP status results, and application-level assertions.
- The MVP MUST NOT claim continuous uptime monitoring unless scheduled execution and monitoring infrastructure are implemented.
- A successful HTTP response alone MUST NOT be described as proof of internal service health.

### 3.3 API explorer and structure analysis

- Import OpenAPI specifications from an uploaded file or URL, subject to security controls.
- Display discovered paths, methods, parameters, request schemas, response schemas, and documented status codes.
- Analyze observed response structures and compare them with declared schemas where possible.
- Clearly identify whether information came from a specification, deterministic extraction, inference, or execution evidence.

### 3.4 Intelligent testing

- Generate positive, negative, boundary, schema-validation, and relevant workflow test candidates.
- Validate generated candidates before execution.
- Execute tests through the shared HTTP execution engine.
- Run deterministic assertions and preserve structured evidence.
- Rank observations using explainable heuristics initially; custom ML is not required for the MVP.
- Select follow-up tests based on prior evidence, novelty, unexpectedness, contract discrepancies, boundary relevance, and exploration value.
- Record why a follow-up was selected and what evidence informed it.
- Respect campaign request budgets, iteration limits, deadlines, and per-request timeouts.

### 3.5 Reporting

The MVP should summarize executed tests, assertions, findings, evidence, campaign state, and useful coverage indicators. Metrics must be accurately defined; the product must not claim coverage that it has not measured.

## 4. Approved Frontend

### 4.1 Technology

- React
- Vite
- TypeScript
- React Router
- Tailwind CSS with centralized theme tokens
- CSS variables for authoritative global design values
- TanStack Query for server-state management when API integration begins
- React Hook Form and Zod where useful for forms and validation

Any additional library must solve a concrete need and be documented in the relevant package manifest.

### 4.2 Primary destinations

The frontend has six primary destinations:

1. Overview
2. API Workspace
3. Health Checks
4. API Explorer
5. Test Campaigns
6. Findings & Evidence

Supporting workspace destinations include Collections, Environments, and Request History. Authentication pages such as Login are supporting routes.

### 4.3 Frontend architecture rules

- Route definitions MUST be centralized in the application router.
- Shared navigation and page framing MUST live in shared layouts.
- Global visual values MUST come from centralized design tokens and theme configuration.
- Reusable primitives MUST live in the shared UI component library.
- Pages MUST compose shared components rather than duplicate global styling or component implementations.
- Page-specific styling is allowed only for genuine feature-specific layout; it MUST NOT redefine global design rules.
- Networking logic MUST live in service/API modules, not be duplicated inside page components.
- Frontend API types MUST derive from or remain compatible with the approved API contracts. Generate types from OpenAPI where practical.
- Demo data MUST be isolated behind mock services or fixtures. Demo behavior MUST be clearly distinguishable from real network execution.
- Routes MUST support direct navigation and refresh, with an explicit not-found route.
- Loading, empty, error, and success states MUST be designed for relevant workflows.
- Secrets MUST NOT be embedded in the frontend bundle.

## 5. Approved Backend and Infrastructure Stack

- Python
- FastAPI
- Pydantic for request/response validation
- PostgreSQL
- SQLAlchemy
- Alembic migrations
- HTTPX or another explicitly approved HTTP client for outbound API execution
- pytest for backend tests
- Docker and Docker Compose
- GitHub Actions for CI/CD

The backend is a **modular monolith**, not a microservice fleet. Module boundaries should be explicit in code and dependencies, while the initial deployment can run as one API service plus the database and frontend.

### 5.1 Planned backend modules

- `auth`
- `projects`
- `api_understanding`
- `knowledge`
- `test_generation`
- `execution`
- `analysis`
- `adaptive`
- `campaigns`
- `evidence`
- `reports`
- `integrations/llm`

Module responsibilities and allowed dependencies will be defined in `TECHNICAL_DESIGN.md` and the scaffold instructions. These names are architectural boundaries, not permission to create circular imports or duplicate business logic.

### 5.2 Backend rules

- Keep HTTP route handlers thin: validate input, invoke application/service logic, and map results to API responses.
- Keep domain logic out of route handlers and ORM models.
- Use Pydantic schemas for external request/response contracts and SQLAlchemy models for persistence.
- Use Alembic for schema changes; do not rely on manual production database edits.
- Centralize configuration and validate required environment variables at startup.
- Use consistent error response formats and structured logging.
- Do not log credentials, authorization headers, sensitive request bodies, or provider secrets.
- Define transaction boundaries and ownership checks explicitly.
- Avoid circular module dependencies.
- External provider integrations MUST be behind adapters/interfaces.
- Do not add Redis, Celery, a vector database, a graph database, Kubernetes, or microservices without a documented requirement and approved decision.

## 6. Authentication and Authorization

The approved direction is Google sign-in, verified by FastAPI, with an application session.

- Google identity verification MUST happen on the trusted backend or through a documented secure identity flow.
- Google identity tokens MUST be validated for signature, issuer, audience, expiry, and relevant claims using a supported verification library.
- Google identity is not by itself authorization to access arbitrary application resources.
- The application MUST resolve a stable user identity and enforce authorization on every protected resource.
- Project-owned data MUST be protected by server-side ownership checks.
- The session mechanism, cookie policy, CSRF controls, and deployment-origin configuration will be finalized in the technical design before implementation.
- Prefer secure `HttpOnly` cookies for session credentials when compatible with the selected deployment topology; use `Secure` in HTTPS environments and appropriate `SameSite` settings.
- Do not store long-lived credentials in `localStorage`.
- Never trust a user ID supplied by the frontend as proof of ownership.

## 7. Database and Persistence

- PostgreSQL is the authoritative application database.
- SQLAlchemy models and Alembic migrations define persisted schema evolution.
- Ownership and relationships must be represented explicitly.
- Use stable identifiers, timestamps, constraints, and appropriate indexes.
- Persist campaign lifecycle state and execution evidence sufficiently to diagnose failures and produce reports.
- Do not assume an in-process background task survives a process restart. Campaign execution and interruption recovery must be designed and documented.
- The exact entity list, constraints, indexes, and retention policies belong in `DATABASE_DESIGN.md`.

## 8. LLM and Adaptive Testing Rules

- LLM provider access MUST be isolated behind a provider adapter.
- Provider credentials MUST be read from backend configuration and never exposed to the frontend.
- Prefer structured, schema-validated model output over unvalidated free-form text for machine-consumed decisions.
- Validate generated test candidates before execution.
- Treat model output and imported API descriptions as untrusted input.
- The LLM MUST NOT directly bypass execution safety limits, authentication/authorization, or deterministic validation.
- The system MUST record the evidence used to justify important findings and adaptive follow-up decisions.
- If the provider is unavailable, report the limitation and preserve ordinary API-client functionality. Do not fabricate generated tests or findings.
- Initial interestingness scoring should be explainable and deterministic enough to test.
- Preserve provenance: declared contract, deterministic extraction, inferred hypothesis, and observed evidence must not be conflated.

## 9. Security and Safe API Execution

The application sends requests to user-configured external APIs. This creates a security boundary.

- Require users to be authorized to test their target systems.
- Apply per-request timeouts, request budgets, campaign iteration limits, and response-size limits.
- Protect against SSRF: reject loopback, private, link-local, and other disallowed destinations by default; validate resolved addresses and account for DNS rebinding and redirect behavior.
- Do not allow redirects to bypass destination checks.
- Define explicit handling for non-HTTP(S) schemes; unsupported schemes must be rejected.
- Do not send user credentials or sensitive API data to an LLM provider unless required, disclosed, and permitted by configuration.
- Never expose precise target credentials or secrets in reports and logs.
- Validate uploaded/imported specification size and content; do not blindly fetch arbitrary remote references.
- Use least privilege for database credentials and runtime containers.
- Treat all API responses, imported specifications, and model outputs as untrusted data.
- Security requirements must be tested, not merely documented.

## 10. Containerization and Deployment Readiness

The initial target is containerized local development, not dependence on a particular free hosting service.

- `docker-compose.yml` MUST provide a reproducible local development environment for the frontend, backend, and PostgreSQL.
- Services MUST use environment-based configuration.
- Commit `.env.example`, never real secrets.
- Use production-oriented Docker builds, preferably multi-stage builds, and avoid running containers as root where practical.
- Define health/readiness behavior and service startup dependencies correctly.
- Database migrations must run through a controlled, documented step.
- The system must not depend on a hosted LLM provider to start or to use ordinary API-client features.
- Future deployment topology must be configurable without embedding host-specific assumptions into application code.

## 11. Testing and CI/CD

GitHub Actions is the approved CI/CD system.

### Required CI checks

- Frontend linting, TypeScript checking, tests, and production build.
- Backend linting/formatting checks, type checking where configured, and tests.
- Contract/schema validation.
- Docker image build checks.
- Database migration validation and integration tests as the database foundation is introduced.
- Security-relevant tests for authentication, ownership, request limits, and unsafe target URLs.

### Testing rules

- Unit tests must not require a live LLM provider.
- Use deterministic fixtures and mocked provider responses for normal CI.
- Real provider integration tests must be opt-in and require explicit credentials/configuration.
- Every feature must include tests for its important success and failure cases.
- End-to-end acceptance criteria must cover complete user workflows, not just isolated functions.
- Pull requests must pass required checks before merging.
- Deployment workflow can be added and configured without requiring public hosting during initial development.

## 12. Team Ownership and Collaboration

The user is the integration lead and also owns a major foundational feature area. A second developer owns bounded testing-intelligence modules.

### Integration lead responsibilities

- Maintain source-of-truth documents and architecture decisions.
- Own shared contracts, foundational infrastructure, and integration policy.
- Own authentication/database foundations and the agreed core execution infrastructure unless responsibilities are explicitly reassigned.
- Review changes to shared schemas, central configuration, migrations, and module boundaries.
- Coordinate integration, resolve cross-module failures, and verify release readiness.

### Second developer responsibilities

- Implement assigned intelligence modules against approved contracts.
- Maintain module-specific tests and documentation.
- Avoid modifying shared foundations without review.
- Integrate through pull requests and report contract gaps rather than inventing incompatible interfaces.

### Collaboration rules

- Assign explicit file/directory ownership for each task.
- Keep changes small and focused.
- Use feature branches and pull requests.
- Do not allow two developers or coding agents to concurrently edit the same shared files without coordination.
- Update contracts and tests when a reviewed interface change is necessary.
- A module is complete only when its acceptance criteria and required tests pass.

## 13. Implementation Sequence

1. Finalize source-of-truth and technical design documents.
2. Complete the frontend and routing with typed mock services.
3. Establish backend scaffold, contracts, Docker Compose, and CI.
4. Implement Google authentication and PostgreSQL persistence.
5. Implement and integrate core API utilities.
6. Implement test generation, analysis, evidence, adaptive testing, and reporting.
7. Complete end-to-end verification and deployment readiness.

These are implementation stages, not necessarily separate calendar sprints. The frontend is implemented first, while stable API contracts and architecture are established before independent backend work begins.

## 14. Definition of Done

A feature is not complete merely because its code has been generated.

A feature is done when:

- It follows this source of truth and its module instructions.
- Its public interface matches the approved contract.
- Success, error, and boundary cases are handled.
- Required tests pass.
- It does not introduce secrets, unsafe execution paths, or unauthorized data access.
- Its user-facing behavior distinguishes real operations from demo behavior.
- It is integrated with dependent modules and passes CI.
- Its documentation and known limitations are updated.

## 15. Open Decisions to Resolve in Detailed Design

The following choices are intentionally not invented by this document. Resolve them in the relevant design documents before implementing affected modules:

1. Exact session transport and deployment-origin strategy for Google authentication.
2. Final entity relationships, indexes, deletion behavior, and evidence-retention policy.
3. Exact API paths, schemas, error envelope, pagination, and campaign state transitions.
4. Background campaign execution and restart/recovery strategy.
5. Exact LLM provider, model, quota/cost limits, and structured-output strategy.
6. Exact SSRF policy, DNS/redirect controls, target allowlisting, and response-size limits.
7. Which optional API-client features (for example cURL import/export, advanced OAuth, scripting) fit the MVP time budget.

These decisions do not invalidate the approved baseline; they are detailed design work that must be completed before the affected implementation begins.
