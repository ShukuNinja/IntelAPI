# Experimental Workbench Implementation Audit

**Audit date:** 2026-10-23  
**Branch:** `frontend-backend_integration`  
**Scope:** the existing application paths relevant to a comparable, persisted API-testing workbench.

This audit distinguishes implementation evidence from the requested experimental behavior. The repository's `docs/COMPLETION_LOG.md` records prior backend and frontend verification; those results are historical and are not a claim that this checkout was re-run during this audit.

## Existing architecture and status

| Capability | Status | Evidence and limits |
|---|---|---|
| Frontend and routing | Implemented and previously verified | React/Vite routes in `apps/web/src/app/router.tsx`; authenticated shell and project context in `apps/web/src/components/layout/AppShell.tsx` and `apps/web/src/features/projects/ProjectContext.tsx`. Existing destinations include Explorer, Campaigns, Findings, and Workspace. No Experimental Workbench or experiment comparison view exists. |
| OpenAPI ingestion and normalized operations | Implemented and previously verified | Authenticated import/list/detail/operation routes in `apps/api/app/api/specifications/router.py`; parser and normalizer in `apps/api/app/modules/api_understanding/{parser,normalizer}.py`; JSON/YAML contract coverage in `apps/api/tests/test_api_understanding.py` and persistence acceptance in `apps/api/tests/test_persisted_product_flows.py`. URL imports use the shared execution security boundary. Parsing warnings and complete server/auth metadata are not yet exposed as a purpose-built explorer contract. |
| Semantic knowledge | Implemented, partially integrated | Declared facts are extracted by `apps/api/app/modules/knowledge/extractor.py`, persisted through `KnowledgeFact`, and exposed per operation by the specification API. The candidate generator does not currently receive those facts as generation context, so an Approach B path is missing. |
| Deterministic candidates, validation, deduplication | Implemented and previously verified | `apps/api/app/modules/test_generation/{generator,validation,deduplication}.py`; candidate preview uses these through `preview.py`. Operation campaigns persist deterministic candidates in `apps/api/app/api/campaigns/router.py`. Validation is shared for preview, but candidate validation outcomes are not persisted as experiment records. |
| LLM provider and candidate proposals | Partially implemented | Provider abstraction/factory and NVIDIA adapter live in `apps/api/app/integrations/llm/`; `llm_assisted.py` validates proposals and `orchestration.py` preserves deterministic fallback. Explorer preview can opt into LLM output. Groq is not configured, provider/model/prompt/token/latency metadata is not captured, and campaign generation does not use the LLM path. |
| Shared outbound execution and safety | Implemented and previously verified | `apps/api/app/api/executions/service.py` and `apps/api/app/modules/execution/security.py` enforce the outbound boundary; campaigns reuse it via `apps/api/app/worker.py`. Local target policy, redirect checks, timeouts, byte limits, and sensitive header handling have focused tests in `apps/api/tests/test_execution_security.py`. |
| Assertions and findings | Implemented, partially integrated | OpenAPI assertion extraction is in `apps/api/app/modules/assertion_analysis/analyzer.py`; campaign assertions/evidence are recorded by the worker and findings APIs. Outcomes do not yet form an experiment-level diagnosis dataset with ground truth or diagnosis accuracy. |
| Adaptive feedback | Implemented in campaign worker | `apps/api/app/modules/adaptive/scorer.py` ranks candidates; `apps/api/app/worker.py` records `adaptive_candidate_selected` events using prior executions/findings. This is a feedback loop over a pre-generated pool, not iterative generation. It is not selectable as an explicit experiment approach. |
| Durable campaigns and results | Implemented and previously verified | Alembic revisions `0006_testing_campaigns` and `0007_findings_evidence`; models in `apps/api/app/models/campaign.py`; owner-checked campaign APIs in `apps/api/app/api/campaigns/router.py`; a separate worker in `apps/api/app/worker.py`. Campaigns support request or operation testing, bounded execution, cancellation, events, and reports. |
| Experiments, approach runs, comparison metrics | Missing | No experiment/approach-run persistence or API exists. Campaign reports contain counts, not a shared metric contract for validity, selected-operation coverage, constraint coverage, confirmed defects, cost, or unavailable metric reasons. |
| Frontend experimentation flow | Missing | `apps/web/src/features/campaigns/CampaignsPage.tsx` starts one campaign policy and displays its report. `ExplorerPage.tsx` imports and previews contracts. Neither supports approach selection, comparative execution, durable experiment history, or export. |
| Automated validation in this environment | Not verified in this audit | Docker is installed but the Docker Desktop engine is unavailable. The host has Python 3.11.9 while `apps/api/pyproject.toml` requires Python 3.12+. Historical test/build results are recorded in `docs/COMPLETION_LOG.md`; local revalidation requires the project runtime or a reachable Docker engine. |

## Workbench implementation direction

Reuse project ownership, specification and knowledge records, candidate validation, campaign jobs, the secured execution service, assertions, findings, and adaptive events. Add a persisted experiment layer that groups comparable approach runs and derives metrics from their actual campaign/test/execution records. Keep provider errors and generated text bounded and secret-safe. An approach is complete only when its distinct policy and configuration are recorded and its real execution path can be inspected; unavailable metrics must include a reason.

## Baseline constraints observed

- No test was run by this audit; the environment's Python and Docker runtime do not meet the repository's declared backend test setup.
- No live provider credentials or target API were used.
- The existing current branch is `frontend-backend_integration`; the worktree was clean before this task.
