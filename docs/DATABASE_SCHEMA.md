# IntelAPI — Frozen Database Schema Contract

**Version:** 1.0
**Baseline:** 2026-10-16
**Status:** Accepted logical schema for implementation. This document defines the target model, not tables already present in the repository. `SOURCE_OF_TRUTH.md` governs product rules; this document governs table shape and migration ordering. Developer A is the sole migration author/merger.

## 1. Global conventions

- PostgreSQL; SQLAlchemy 2.x typed ORM; Alembic-only schema changes.
- UUID primary keys unless a table is explicitly a join/child table whose own UUID is still useful for stable references.
- `created_at` and `updated_at` use timezone-aware timestamps (`timestamptz`) where applicable; UTC at application boundaries.
- Use database foreign keys and indexes for ownership paths. Never rely only on frontend filtering.
- Public API schemas are separate from ORM models.
- All project-scoped records must be reachable through a project ownership check, directly or through a parent relationship.
- JSONB is appropriate for bounded, versioned structured snapshots; never store unbounded bodies/specs.
- Secret material is encrypted at rest using a server-side key; only ciphertext is stored. Plaintext is never returned after write.
- Exact physical types may use SQLAlchemy equivalents, but semantics, nullability, uniqueness, relationships, and constraints below are normative.

## 2. Tables

### 2.1 Identity and projects

#### `users`
- `id UUID PK`
- `google_sub VARCHAR(255) NOT NULL UNIQUE` — stable Google identity key.
- `email VARCHAR(320) NULL`, `display_name VARCHAR(200) NULL`, `avatar_url TEXT NULL`
- `created_at TIMESTAMPTZ NOT NULL`, `updated_at TIMESTAMPTZ NOT NULL`
- Email is not the identity key. Do not require email to be globally unique as an identity guarantee.

#### `sessions`
- `id UUID PK`, `user_id UUID NOT NULL FK users.id ON DELETE CASCADE`
- `token_hash BYTEA NOT NULL UNIQUE` — hash of a high-entropy opaque token, never raw token.
- `created_at TIMESTAMPTZ NOT NULL`, `expires_at TIMESTAMPTZ NOT NULL`, `revoked_at TIMESTAMPTZ NULL`, `last_seen_at TIMESTAMPTZ NULL`
- Index `(user_id, expires_at)`; active session predicate is `revoked_at IS NULL AND expires_at > now()`.

#### `projects`
- `id UUID PK`, `owner_user_id UUID NOT NULL FK users.id ON DELETE RESTRICT`
- `name VARCHAR(120) NOT NULL`, `description TEXT NULL`
- `created_at`, `updated_at` `TIMESTAMPTZ NOT NULL`; `deleted_at TIMESTAMPTZ NULL`
- Index `(owner_user_id, deleted_at, updated_at DESC)`.
- Archive sets `deleted_at`; no permanent-delete endpoint in MVP. Do not cascade-delete historical executions/campaigns on archive.

### 2.2 Workspace resources

#### `collections`
- `id UUID PK`, `project_id UUID NOT NULL FK projects.id ON DELETE RESTRICT`
- `name VARCHAR(120) NOT NULL`, `description TEXT NULL`, timestamps
- Unique `(project_id, name)`; index `(project_id, updated_at DESC)`.

#### `saved_requests`
- `id UUID PK`, `project_id UUID NOT NULL FK projects.id ON DELETE RESTRICT`
- `collection_id UUID NULL FK collections.id ON DELETE SET NULL`
- `name VARCHAR(160) NOT NULL`, `method VARCHAR(12) NOT NULL`, `url_template TEXT NOT NULL`
- `headers JSONB NOT NULL DEFAULT '{}'`, `query_params JSONB NOT NULL DEFAULT '{}'`, `body JSONB NULL`
- `auth_config JSONB NULL` — references secret variables where possible; must not store plaintext credentials.
- `created_at`, `updated_at` timestamps
- Index `(project_id, updated_at DESC)`, `(collection_id)`.

#### `environments`
- `id UUID PK`, `project_id UUID NOT NULL FK projects.id ON DELETE RESTRICT`
- `name VARCHAR(120) NOT NULL`, `base_url TEXT NULL`, `created_at`, `updated_at`
- Unique `(project_id, name)`.

#### `environment_variables`
- `id UUID PK`, `environment_id UUID NOT NULL FK environments.id ON DELETE CASCADE`
- `key VARCHAR(160) NOT NULL`, `value_ciphertext BYTEA NULL`, `value_plain TEXT NULL`, `is_secret BOOLEAN NOT NULL DEFAULT false`
- `created_at`, `updated_at`
- Unique `(environment_id, key)`.
- Exactly one of `value_ciphertext` or `value_plain` is populated. `is_secret=true` requires ciphertext. API writes accept plaintext only transiently, encrypt before persistence, and never return the secret value.

### 2.3 Execution and API understanding

#### `executions`
- `id UUID PK`, `project_id UUID NOT NULL FK projects.id ON DELETE RESTRICT`
- `saved_request_id UUID NULL FK saved_requests.id ON DELETE SET NULL`
- `campaign_id UUID NULL` (FK added in campaign migration after `campaigns` exists; alternatively create nullable FK in the same migration that introduces both tables)
- `test_case_id UUID NULL` (FK added when `test_cases` exists)
- `outcome VARCHAR(32) NOT NULL` — `http_response`, `timeout`, `connection_error`, `blocked_by_policy`, `response_too_large`, `execution_error`.
- `status_code INTEGER NULL`, `duration_ms INTEGER NULL`, `started_at TIMESTAMPTZ NOT NULL`, `completed_at TIMESTAMPTZ NULL`
- `request_snapshot JSONB NOT NULL` — immutable, resolved, redacted request snapshot.
- `response_status INTEGER NULL`, `response_headers JSONB NULL`, `response_excerpt TEXT NULL`, `response_size_bytes BIGINT NULL`, `transport_error_code VARCHAR(64) NULL`
- `environment_id UUID NULL FK environments.id ON DELETE SET NULL`; `specification_version_id UUID NULL` (FK added with specifications)
- Index `(project_id, started_at DESC)`, `(campaign_id, started_at)`, `(test_case_id)`.
- A non-2xx HTTP response remains `outcome='http_response'`; assertion results determine test pass/fail.

#### `assertion_results`
- `id UUID PK`, `execution_id UUID NOT NULL FK executions.id ON DELETE CASCADE`
- `assertion_type VARCHAR(32) NOT NULL`, `passed BOOLEAN NOT NULL`, `expected JSONB NULL`, `actual JSONB NULL`, `message TEXT NOT NULL`
- `created_at TIMESTAMPTZ NOT NULL`; index `(execution_id)`.

#### `api_specifications`
- `id UUID PK`, `project_id UUID NOT NULL FK projects.id ON DELETE RESTRICT`
- `name VARCHAR(160) NOT NULL`, `source_kind VARCHAR(16) NOT NULL` (`file` or `url`), `source_url TEXT NULL`
- `spec_document JSONB NOT NULL` — bounded original parsed document.
- `content_sha256 CHAR(64) NOT NULL`, `spec_version INTEGER NOT NULL`, `openapi_version VARCHAR(32) NULL`
- `created_at TIMESTAMPTZ NOT NULL`, `created_by_user_id UUID NOT NULL FK users.id ON DELETE RESTRICT`
- Unique `(project_id, content_sha256)` unless product intentionally allows duplicate imports; default policy is deduplicate identical content within project.
- Index `(project_id, created_at DESC)`.

#### `api_operations`
- `id UUID PK`, `specification_id UUID NOT NULL FK api_specifications.id ON DELETE CASCADE`
- `operation_key VARCHAR(255) NOT NULL`, `method VARCHAR(12) NOT NULL`, `path_template TEXT NOT NULL`
- `summary TEXT NULL`, `operation_document JSONB NOT NULL` — bounded normalized source fragment.
- `created_at TIMESTAMPTZ NOT NULL`
- Unique `(specification_id, operation_key)`; index `(specification_id, path_template)`.

#### `knowledge_facts`
- `id UUID PK`, `project_id UUID NOT NULL FK projects.id ON DELETE RESTRICT`
- `specification_id UUID NULL FK api_specifications.id ON DELETE SET NULL`, `operation_id UUID NULL FK api_operations.id ON DELETE SET NULL`, `execution_id UUID NULL FK executions.id ON DELETE SET NULL`
- `fact_type VARCHAR(80) NOT NULL`, `subject VARCHAR(255) NOT NULL`, `fact_value JSONB NOT NULL`
- `provenance VARCHAR(16) NOT NULL` — `DECLARED`, `EXTRACTED`, `OBSERVED`, `INFERRED`.
- `confidence NUMERIC(4,3) NULL` constrained to `[0,1]`; `created_at TIMESTAMPTZ NOT NULL`
- Index `(project_id, operation_id, fact_type)`.

### 2.4 Health checks and campaigns

#### `health_checks`
- `id UUID PK`, `project_id UUID NOT NULL FK projects.id ON DELETE RESTRICT`, `saved_request_id UUID NULL FK saved_requests.id ON DELETE SET NULL`
- `name VARCHAR(160) NOT NULL`, `definition JSONB NOT NULL` — request reference/definition plus bounded assertion configuration.
- `enabled BOOLEAN NOT NULL DEFAULT true`, `created_at`, `updated_at`
- Index `(project_id, enabled, updated_at DESC)`.

Health-check run history uses `executions` plus `assertion_results`; do not add a second parallel execution record model in MVP.

#### `test_cases`
- `id UUID PK`, `project_id UUID NOT NULL FK projects.id ON DELETE RESTRICT`, `campaign_id UUID NOT NULL FK campaigns.id ON DELETE CASCADE` (migration must create this relationship consistently with campaign table ordering)
- `operation_id UUID NULL FK api_operations.id ON DELETE SET NULL`
- `candidate_key VARCHAR(255) NOT NULL`, `category VARCHAR(32) NOT NULL`, `title VARCHAR(200) NOT NULL`, `description TEXT NULL`
- `request_override JSONB NOT NULL`, `expected_behavior JSONB NULL`, `generation_provenance VARCHAR(16) NOT NULL`
- `created_at TIMESTAMPTZ NOT NULL`
- Unique `(campaign_id, candidate_key)`; index `(campaign_id, created_at)`.

#### `campaigns`
- `id UUID PK`, `project_id UUID NOT NULL FK projects.id ON DELETE RESTRICT`, `created_by_user_id UUID NOT NULL FK users.id ON DELETE RESTRICT`
- `name VARCHAR(160) NOT NULL`, `state VARCHAR(16) NOT NULL` (`queued`, `running`, `completed`, `failed`, `cancelled`)
- `configuration JSONB NOT NULL` — bounded generation/selection/budget configuration.
- `budget_max_executions INTEGER NOT NULL`, `budget_max_iterations INTEGER NOT NULL`, `budget_max_duration_seconds INTEGER NOT NULL`
- `started_at TIMESTAMPTZ NULL`, `completed_at TIMESTAMPTZ NULL`, `cancel_requested_at TIMESTAMPTZ NULL`
- `failure_code VARCHAR(64) NULL`, `failure_summary TEXT NULL`, `created_at`, `updated_at`
- Index `(project_id, created_at DESC)`, `(state, created_at)`.

#### `campaign_jobs`
- `id UUID PK`, `campaign_id UUID NOT NULL UNIQUE FK campaigns.id ON DELETE CASCADE`
- `state VARCHAR(16) NOT NULL` (`queued`, `leased`, `completed`, `failed`, `cancelled`)
- `available_at TIMESTAMPTZ NOT NULL`, `lease_owner VARCHAR(160) NULL`, `lease_expires_at TIMESTAMPTZ NULL`, `attempt_count INTEGER NOT NULL DEFAULT 0`
- `last_error_code VARCHAR(64) NULL`, `created_at`, `updated_at`
- Index `(state, available_at)`, `(lease_expires_at)`.
- Claim/lease transition occurs in a transaction using row locking (`FOR UPDATE SKIP LOCKED` where appropriate). Lease expiry permits recovery, not blind re-execution of an uncertain target request.

#### `campaign_events`
- `id UUID PK`, `campaign_id UUID NOT NULL FK campaigns.id ON DELETE CASCADE`
- `sequence_number BIGINT NOT NULL`, `event_type VARCHAR(80) NOT NULL`, `payload JSONB NOT NULL`, `created_at TIMESTAMPTZ NOT NULL`
- Unique `(campaign_id, sequence_number)`; index `(campaign_id, created_at)`.
- Append-only at application level. Do not update or delete historical events during normal operation.

### 2.5 Findings and evidence

#### `findings`
- `id UUID PK`, `project_id UUID NOT NULL FK projects.id ON DELETE RESTRICT`, `campaign_id UUID NULL FK campaigns.id ON DELETE SET NULL`
- `test_case_id UUID NULL FK test_cases.id ON DELETE SET NULL`, `execution_id UUID NULL FK executions.id ON DELETE SET NULL`
- `finding_key VARCHAR(255) NOT NULL`, `title VARCHAR(240) NOT NULL`, `summary TEXT NOT NULL`
- `classification VARCHAR(48) NOT NULL`, `machine_severity VARCHAR(16) NOT NULL`, `confidence NUMERIC(4,3) NULL`
- `user_status VARCHAR(24) NOT NULL DEFAULT 'open'`, `user_severity VARCHAR(16) NULL`, `triage_note TEXT NULL`
- `created_at`, `updated_at`; unique `(project_id, finding_key)`; index `(project_id, user_status, created_at DESC)`.
- Classifier-owned fields and user-managed triage fields remain separate. PATCH cannot overwrite machine-derived classification/confidence/evidence.

#### `evidence_references`
- `id UUID PK`, `project_id UUID NOT NULL FK projects.id ON DELETE RESTRICT`, `finding_id UUID NULL FK findings.id ON DELETE CASCADE`
- `execution_id UUID NULL FK executions.id ON DELETE SET NULL`, `assertion_result_id UUID NULL FK assertion_results.id ON DELETE SET NULL`
- `specification_id UUID NULL FK api_specifications.id ON DELETE SET NULL`, `operation_id UUID NULL FK api_operations.id ON DELETE SET NULL`, `knowledge_fact_id UUID NULL FK knowledge_facts.id ON DELETE SET NULL`
- `provenance VARCHAR(16) NOT NULL` (`DECLARED`, `EXTRACTED`, `OBSERVED`, `INFERRED`)
- `evidence_type VARCHAR(80) NOT NULL`, `excerpt TEXT NULL`, `metadata JSONB NOT NULL DEFAULT '{}'`, `created_at TIMESTAMPTZ NOT NULL`
- Index `(project_id, finding_id)`, `(execution_id)`.
- At least one source FK must be non-null. Enforce with a database check constraint where practical and validate in the service layer. Excerpts must be bounded and redacted.

## 3. Relationship and deletion policy

- `users → projects`: restrict hard deletion while project history exists; account deletion is out of MVP scope.
- `projects → saved resources`: restrict hard delete; archive via `deleted_at`.
- `campaigns → jobs/tests/events`: cascade is acceptable only as part of a future explicit retention/deletion operation; no public campaign hard-delete endpoint in MVP.
- Evidence/finding source links use `SET NULL` where preserving a finding is more important than retaining a source FK, but normal MVP flows do not hard-delete source records.
- Project ownership is verified server-side for every route, including indirect IDs (execution, operation, campaign, finding, evidence).

## 4. Migration order

`0001_initial` is the empty baseline. Applied revisions are sequential and must not be renamed or rewritten. Current domain milestones include `0002_identity_projects`, `0003_api_specifications`, `0004_execution_records`, `0005_generation_reports`, `0006_specification_source_url`, `0007_execution_reports`, `0008_request_resources`, `0009_finding_triage`, `0010_health_checks`, `0011_environment_secrets`, `0012_campaigns`, and `0013_collections`. Add future revisions after inspecting `alembic history`, `alembic heads`, and `alembic current`; preserve a single head and update this document alongside schema changes.

## 5. Required indexes and constraints checklist

- Unique `users.google_sub`; unique `sessions.token_hash`.
- Project ownership indexes; soft-delete-aware project listing.
- Unique collection/environment names within project.
- Unique environment variable key within environment.
- Unique API operation key within specification; dedupe specs by project/content hash by default.
- Unique candidate key within campaign; unique campaign job per campaign; unique event sequence per campaign.
- Finding key unique within project.
- FK constraints and checks for allowed enum values, confidence range, valid campaign states, and environment secret ciphertext semantics.
- Index every high-volume foreign key and list query path; avoid adding speculative indexes without query justification.

## 6. Not permitted

- `Base.metadata.create_all()` as a migration substitute.
- Storing plaintext environment secrets or raw session tokens.
- Treating denormalized counters as authoritative in MVP.
- Adding a separate health-run table when `executions` and `assertion_results` suffice.
- Adding finding status history in MVP; `campaign_events` is append-only and no dedicated finding-history table is approved.
- Adding roles/organizations/tenancy hierarchy not approved in `SOURCE_OF_TRUTH.md`.
