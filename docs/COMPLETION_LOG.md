# Application Completion Log

This is the running delivery log for completing IntelAPI. Entries record source-backed work and verification; a feature is not marked complete merely because a screen, route, or domain helper exists.

## 2026-10-21 — Baseline and first integration slice

### Verified baseline

- The supplied audit ZIP and current checkout agree that the API currently persists users/sessions, projects, collections, saved requests, environments/variables, executions, and execution evidence.
- Existing API-backed flows include Google session auth, project CRUD/archive, collection CRUD, saved request CRUD, environment CRUD/upsert-variable, one-off execution, persisted saved-request execution, and execution history.
- Domain helpers exist for OpenAPI parsing, knowledge extraction, candidate generation/preview, assertion analysis, classification, and adaptive scoring. Product APIs and durable tables are still missing for specifications/operations/knowledge facts, health checks, test cases/campaigns/jobs/events, findings/evidence references, and report aggregates.
- The prior deletion of `docs/IMPLEMENTATION_STATUS.md` was present before this log was created and has been preserved.

### Implemented in this work session

- Added a project context and selector, keeping the active project in browser storage.
- Connected the request workspace to saved-request CRUD and persisted execution, including collection/environment association and request history.
- Added API-backed Collections, Environments, and Request History screens.
- Replaced static overview fixture data with saved-request and persisted-execution data from the active project.
- Improved API error messages and avoided setting JSON content type on non-string request bodies.

### Verification

- `npm run typecheck --prefix apps/web` — passed.
- `npm run build --prefix apps/web` — passed.
- `npm run lint --prefix apps/web` — passed with three Fast Refresh warnings (one in the new project context and two pre-existing warnings).
- `git diff --check` — passed; Git reported only line-ending normalization notices.
- Backend tests, migrations, live PostgreSQL, Google sign-in, browser E2E, and target API requests have not been verified.

### Remaining delivery plan (dependency order)

1. Complete workspace integration edge cases and confirm DB/migration baseline.
2. Persist OpenAPI specifications, normalized operations, and extracted knowledge facts; expose ownership-checked import/list/detail/operation APIs and non-persisting candidate preview; connect Explorer.
3. Implement persisted health-check definitions/assertion results/runs and connect Health Checks.
4. Implement durable test/campaign/job/event persistence and worker lifecycle, cancellation/recovery/budgets, APIs, and connect Campaigns.
5. Implement findings/evidence references, evidence-backed triage APIs, and campaign reports; connect Findings & Evidence.
6. Replace any remaining demo or placeholder product flows, add acceptance coverage, verify clean Alembic upgrade, and update this log with actual results.

### Scope constraint from user

- The user initially requested no schema changes, then explicitly authorized the changes required to complete the application. That later authorization controls; additive Alembic migrations are now in scope.

### Authorization update

- User has now explicitly authorized all needed code, API, and database schema changes for completing the application. The schema freeze above is lifted. Continue to use Alembic migrations and preserve the product invariants in `SOURCE_OF_TRUTH.md` and `DATABASE_SCHEMA.md`.

## 2026-10-21 — Updated working branch from `main`

- Preserved the uncommitted integration work in a Git stash before updating; reapplied it successfully afterward with no conflicts. The stash remains as a recovery backup.
- Fast-forwarded `frontend-backend_integration` to `eb67efe` (`origin/main`). The branch name remains `frontend-backend_integration`; no merge from this branch into `main` was performed.
- Re-inspected `apps/api/app/api`, `apps/api/app/models`, and `apps/api/alembic/versions` on the updated base. The product APIs and durable tables for specifications, health checks, campaigns, findings, and reports are still absent.
- No database or backend API schema changes were made while updating the branch.
- `npm run typecheck --prefix apps/web` — passed.
- `npm run build --prefix apps/web` — passed.
- `npm run lint --prefix apps/web` — passed with three Fast Refresh warnings and no errors.
- `git diff --check` — passed; Git emitted only line-ending normalization notices.

## 2026-10-21 — Specification Explorer and health checks

### Implemented

- Added additive persistence for API specifications, normalized operations, extracted knowledge facts, health-check definitions, and assertion results in Alembic revision `0005_api_understanding_health`.
- Added authenticated, project-owner-checked API routes for spec import/list/detail/operations/facts and deterministic or optional LLM candidate previews. URL imports use the existing outbound destination checks and response-size limits; remote `$ref` values remain rejected.
- Connected API Explorer to persisted specifications, JSON/YAML file or URL import, operation browsing, and non-persisting candidate preview.
- Added health-check create/list/read/update/delete/run/result APIs. Runs use persisted saved requests and append their assertions to the existing execution history.
- Replaced health-check sample data with project-backed checks, request selection, run actions, result details, and error reporting.

### Verification

- Applied `0005_api_understanding_health` to the development PostgreSQL database with `alembic upgrade head` — passed.
- Backend Ruff checks for changed API/model files — passed.
- Full existing API pytest suite — 225 passed, 6 upstream/deprecation warnings.
- Frontend TypeScript check and production build — passed.

### Remaining at that milestone

- Add route-level acceptance tests for the new endpoints and persisted migration path.
- Implement durable campaign creation, queue/job/event lifecycle, separate worker, bounded execution, and reports.
- Implement evidence-backed findings/triage and connect remaining frontend screens.
- Verify the full application against a clean database and complete browser-level acceptance flows.

## 2026-10-21 — Campaigns, findings, runtime, and acceptance coverage

### Implemented

- Added `0006_testing_campaigns` and `0007_findings_evidence` as additive migrations, preserving the existing ancestry. They persist campaigns, test cases, durable leased jobs, append-only events, execution links, findings, and source references.
- Added owner-checked campaign APIs for create/list/detail/cancel, tests, executions, events, and derived report. Campaign creation stores its test cases, job, and first event in one transaction and returns `202`.
- Added a separate Compose `worker` process. It claims jobs with PostgreSQL row locks, observes execution/time/iteration budgets, checks cancellation between requests, and records progress events. Before a target call it commits a start event; lease recovery marks an unrecorded in-flight call uncertain rather than retrying it.
- Connected Campaigns to saved requests and optional environments, with queued/running status refresh, cancel, event timeline, and report views.
- Added findings/evidence APIs. Failed configured health assertions create deduplicated potential findings with declared and observed evidence sources; triage updates can change only user-managed fields.
- Connected Findings & Evidence to real records, severity/status filters, evidence inspection, triage, and JSON export. Replaced the final Settings placeholder with account/project/service status and sign-out; removed unused demo fixture modules.
- Added API acceptance tests for specification persistence and preview, campaign creation/cancellation, a simulated exactly-once worker run, health assertion persistence, evidence creation, and protected triage.

### Verification and runtime

- Alembic upgrade completed at `0007_findings_evidence` (head) on the development PostgreSQL database.
- Backend Ruff — passed. Backend pytest — 230 passed, 6 framework deprecation warnings. Coverage includes transport failures remaining `unavailable` observations rather than potential findings.
- Frontend typecheck and production build — passed. ESLint — no errors, three Fast Refresh warnings (one in ProjectContext and two pre-existing).
- `git diff --check` — passed; Git reported only CRLF normalization notices.
- Rebuilt API/web containers; API `/health/ready` and web root both returned 200, and the worker process started. Google sign-in config is present (the client ID is not recorded here).
- No merge into `main` was performed. Work remains on `frontend-backend_integration`.

### Known product limitations / remaining acceptance at this milestone

The following state was current before the later OpenAPI campaign implementation recorded below.

- Campaign inputs currently run one baseline execution per selected saved request. Generated operation candidates and adaptive follow-up selection are not yet part of campaign execution; candidate generation is available as a non-persisting Explorer preview.
- Findings are currently created from failed configured health assertions. Campaign execution findings and schema-comparison findings are not yet generated.
- The new Alembic chain was upgraded on the development DB; a fresh isolated database migration and authenticated browser E2E with a real Google session have not been run.
- Continue with operation-based test execution/adaptive iteration, campaign-to-finding classification, and full browser acceptance before calling the product fully complete.

## Entry template

For each subsequent milestone, append the date, changed capabilities/files, migration impact, verification commands/results, known limitations, and the next concrete milestone. Keep credentials and secret values out of this file.

## 2026-10-21 — OpenAPI-backed campaign execution

### Implemented

- Extended campaign creation to accept either project-owned saved requests or project-owned OpenAPI operations. Operation campaigns require a project environment with a base URL and persist deterministic positive, negative, boundary, and schema candidate cases within execution/iteration budgets.
- Routed OpenAPI candidates through the same guarded outbound execution service as saved requests, including project/environment ownership checks, URL destination validation, variable substitution, time/response limits, and execution evidence.
- Evaluated declared successful-response status/property assertions for completed HTTP responses. Persisted assertion results and evidence-backed campaign findings for supported mismatches; transport failures remain execution failures and do not create defect findings.
- Wired the existing adaptive ranker into the durable worker loop. After each execution, it selects the next pending OpenAPI case using observed findings, status inconsistency, category novelty, boundary relevance, and request risk, then persists a rationale and evidence-linked `adaptive_candidate_selected` event.
- Connected the Campaigns screen to operation selection and environment selection while preserving saved-request campaigns.
- No database migration or table change was needed; this work uses the campaign, test-case, execution, assertion-result, finding, and evidence tables already introduced in `0005`–`0007`.

### Verification and runtime

- Backend Ruff — passed. Backend pytest — 232 passed, 6 framework/deprecation warnings. Acceptance coverage includes a simulated OpenAPI worker run that records failed schema assertions and operation-linked finding evidence, then selects a schema follow-up using that evidence.
- Frontend TypeScript typecheck and production build — passed. ESLint — zero errors and three Fast Refresh warnings.
- `git diff --check` — passed (line-ending normalization notices only).
- Development database and a newly created isolated acceptance database both reached `0007_findings_evidence (head)`; the isolated upgrade started from an empty database. API readiness and web root returned HTTP 200 after restarting API/worker and deploying the locally built web assets.
- Docker Hub reset the connection during web image rebuild. The verified local `dist` was copied into the container, committed to the local service image, and the web container was recreated successfully. A clean source image build still requires Docker Hub connectivity.

### Remaining acceptance before calling the whole product complete

- Run authenticated browser end-to-end acceptance with a real Google session. The browser is currently on `/login`; the computer-use skill prohibits automating authentication dialogs, so the user must sign in manually before this check can continue.
- Verify a representative operation campaign against an approved test target through the UI; automated campaign tests use simulated execution and do not send outbound requests.

## 2026-10-21 — Complete health assertion coverage

### Implemented

- Added bounded deterministic response-schema assertions for object, array, scalar, enum, required-property, and common length/count/range constraints. Schema validation avoids external references and records validity plus redacted violation paths instead of storing the response body as assertion output.
- Completed the Health Checks creation form for status, latency, JSON path/value, response header, and response schema assertions.
- Preserved execution status in health assertion history so reloaded checks distinguish unavailable transport failures from degraded HTTP responses.
- No table or migration change was required; `assertion_results.actual` and the existing JSON definition store the result/schema.

### Verification and runtime

- Backend Ruff — passed. Backend pytest — 233 passed, 6 framework/deprecation warnings; response-schema tests cover both mismatch and valid responses, and transport history covers unavailable state.
- Frontend TypeScript typecheck and production build — passed. ESLint — zero errors, three Fast Refresh warnings.
- Development and isolated acceptance databases remain at Alembic head `0007_findings_evidence`.
- Deployed the rebuilt frontend to the local web image and recreated the web container; web and API returned HTTP 200 after API/worker restart.

### Remaining acceptance

- Authenticated browser end-to-end use and a campaign against an approved non-production target remain unverified because the current browser is signed out at `/login`.

## 2026-10-21 — Campaign report drill-down

### Implemented

- Campaign reports now pair each generated test case with its execution status, response status, duration, redacted response preview, errors, request variation, and expected behavior.
- Campaign execution pages are fetched across the full report rather than stopping at the API's default first page; the UI also shows a notice if the API returns fewer rows than the report total.
- Added shared readable JSON preview styling used by Explorer operation details and campaign execution details.
- No database schema or migration changes.

### Verification

- Frontend TypeScript typecheck — passed.
- Frontend ESLint — zero errors; three existing Fast Refresh warnings.
- Frontend production build — passed.
- Full backend pytest suite — 233 passed, 6 upstream/framework deprecation warnings.
- Local deployment — updated frontend assets copied into the local image and web container recreated; API readiness and web root returned HTTP 200.
- API CORS preflight for the local web origin — HTTP 200 with the expected origin and credentials headers.
- `git diff --check` — passed apart from Git's LF/CRLF normalization notices.

### Remaining acceptance

- Authenticated browser end-to-end use and a campaign against an approved non-production target remain unverified because the browser is signed out at `/login` and no target was supplied. No credentials or target endpoint were added to the log.

## 2026-10-21 — Documentation and migration metadata alignment

### Implemented

- Updated the README and local runbook to describe the integrated frontend/API setup, current acceptance boundary, active feature branch, and no-merge instruction. Kept baseline audit material historical.
- Matched ORM declarations to the two execution indexes already created in migration `0006_testing_campaigns`; no migration was added and the database schema was not changed.

### Verification

- Running PostgreSQL is at `0007_findings_evidence (head)`.
- Alembic `check` — no new upgrade operations detected after ORM metadata alignment.
- Repository-wide backend Ruff — passed after formatting the new migration files and removing an unused import.
- Full backend pytest — 233 passed, 6 framework/deprecation warnings.
- Local web-origin CORS preflight — HTTP 200 with credentialed origin headers.
- Current local stack — database/API/worker/web containers running; API readiness and web root both returned HTTP 200.

## 2026-10-21 — Authenticated browser walkthrough and API origin correction

### Implemented

- Rebuilt and redeployed the frontend with `VITE_API_BASE_URL=http://localhost:8000`. The prior local asset bundle omitted this build-time variable, so requests went to the static web origin and attempted to parse the app HTML as JSON.
- Updated the README and current runbook to describe the direct API origin for standalone Vite builds and the current browser verification boundary.

### Verification

- Signed-in browser walkthrough passed for Overview, API Workspace, Health Checks, API Explorer, Test Campaigns, Findings & Evidence, Projects, and Settings. The project selector and active workspace loaded; Settings reported API/database readiness. No API fetch parsing errors remained.
- API and web services both returned HTTP 200 after deploying the correctly configured bundle.
- The signed-in project currently has no saved requests, imported specifications, health checks, campaigns, or persisted findings; the pages show their intended empty states.

### Acceptance pending at this checkpoint

- A live campaign against an approved target was pending at this checkpoint. It was completed in the subsequent end-to-end acceptance entry below.

## 2026-10-21 — End-to-end request and campaign acceptance

### Implemented and demonstrated

- Saved the starter `GET https://httpbin.org/get` request to the signed-in BloodLink project and executed it from API Workspace with its bounded `page=1` and `limit=20` query parameters.
- Verified HTTP 200 and confirmed the result persisted in Request History after navigating away from the workspace.
- Created and ran `httpbin bounded demo campaign` with exactly one selected saved request. The campaign generated one baseline case, the worker completed one execution with HTTP 200, and the durable report showed all five lifecycle events.
- Restarted API and worker after the live run, reopened the persisted report, and verified the test case was linked to its completed execution with response status, duration, and redacted response preview.
- The user explicitly approved the public httpbin test endpoint for this bounded request and campaign. No credentials or API keys were sent.

### Verification

- Authenticated browser smoke walkthrough — Overview, API Workspace, Health Checks, Explorer, Campaigns, Findings & Evidence, Projects, Collections, Environments, Request History, and Settings loaded from the API without the HTML-as-JSON failure.
- Full backend suite — 233 passed, 6 framework/deprecation warnings.
- Backend Ruff — passed; frontend typecheck, lint (0 errors, 3 Fast Refresh warnings), and production build — passed.
- Alembic current — `0007_findings_evidence (head)`; Alembic check — no new upgrade operations detected. No schema migration was added in this acceptance pass.
- Local API readiness, web root, and authenticated Settings connectivity indicator all reported ready/HTTP 200.

### Remaining limits

- This verifies the complete MVP path against the approved public test service. It does not validate a customer-specific target API, credentials, or its contract. Use a representative non-production customer target for that separate acceptance when one is configured.

## 2026-10-23 — Experimental workbench foundation

### Implemented

- Added `0008_experimental_workbench` with project-owned experiment snapshots and per-approach runs linked to the existing durable campaign records.
- Added authenticated experiment creation, history, detail, and comparison APIs. One experiment is pinned to one specification hash and shares operation selection, categories, environment, and execution budgets across its selected approaches.
- Added separate generation behavior for LLM baseline, semantic-assisted, feedback-guided, and evidence-backed runs. The baseline excludes semantic facts; semantic-assisted generation receives persisted extracted facts. LLM use is explicitly opt-in and falls back to a deterministic candidate pool when disabled, unavailable, empty, or invalid.
- Integrated candidate parameter values into campaign request construction while restricting LLM parameters to declared non-sensitive operation parameters.
- Kept baseline approaches in fixed candidate order, wired feedback-guided runs to the existing adaptive selector, and added a separately weighted evidence/coverage policy with persisted selection rationale and execution references.
- Added shared comparison metrics derived from candidate, execution, assertion, finding, and campaign records. Validity, constraint coverage, ground-truth-dependent rates, token/cost, diagnosis accuracy, and reproducibility return `N/A` with an explicit reason when the required records are not available.
- Added the Experimental Workbench page for selecting specification, operations, target environment, and approaches; starting and cancelling runs; inspecting candidate/request/response evidence and durable selection events; comparing metrics; and exporting comparison JSON.
- Added an audit document at `docs/experimental-workbench-audit.md`. Updated the database schema record for the new experiment tables.
- Removed raw LLM response excerpts and provider exception messages from diagnostics in the prior candidate-generation path.

### Verification

- Backend `python -m ruff check .` — passed.
- Backend targeted Ruff formatting check and `python -m compileall -q app` — passed.
- Frontend `npm run typecheck`, `npm run lint`, and `npm run build` — passed; ESLint reports three existing Fast Refresh warnings.
- Added intelligence and API tests for distinct prompts, deterministic fallback, empty LLM responses, four-run persistence, comparison metrics, and project ownership. Backend pytest could not run: the host has Python 3.11.9 and does not have the `pytest` module; Docker Desktop's engine is unavailable, so the project API container could not be used.
- The new Alembic revision was not applied or checked against PostgreSQL in this environment.

### Known limitations

- Provider cost cannot be estimated because provider pricing is not maintained. Candidate validation failures are not persisted, so validity rate is `N/A`.
- Constraint IDs are not attached to executions, and there is no labeled ground truth, triage event history, or repeat-trial configuration. Related metrics remain `N/A`.
- Approach runs share the configured target but the workbench cannot reset target state. The UI warns users to use an isolated target; stateful comparisons may be contaminated.
- LLM proposals are validated for bounded JSON, operation, category, candidate structure, and declared parameters. Request-body compatibility is not yet a complete JSON Schema validation implementation.
- The initial implementation did not include a controlled fixture experiment or authenticated browser walkthrough.

### 2026-10-23 follow-up — provider selection and acceptance

- Added NVIDIA and Groq provider selection, model overrides, server-side key-presence reporting, and timeout/retry bounds. Keys remain server-side and are never included in provider-option responses.
- Recorded provider, model, and complete token usage when the provider returns it. Cost remains `N/A` with an explanation because pricing is not maintained.
- Applied migration `0008_experimental_workbench` to the local development database.
- Fixed stale candidate/provider test expectations and added Groq, factory, provider-options, and usage-metadata coverage.
- Backend suite: 244 passed. Ruff and Python compilation passed. Frontend typecheck and production build passed; lint has three existing Fast Refresh warnings.
- Authenticated browser walkthrough reached the live workbench and verified provider availability/model controls. No experiment was submitted because the selected BloodLink project has no configured target environment.
