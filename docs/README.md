# IntelAPI — Canonical Development Documentation

**Documentation baseline:** 2026-10-16
**Status:** Accepted product/architecture decisions; implementation status reflects the last verified repository snapshot, not a fresh checkout.

This folder replaces the previous overlapping project documents. Keep these five documents as the canonical set:

| Document | Authority |
|---|---|
| [`PROJECT_HANDOFF.md`](PROJECT_HANDOFF.md) | As-built product, architecture, deterministic engines, feature behavior, metrics, terminology, and known implementation limits |
| [`SOURCE_OF_TRUTH.md`](SOURCE_OF_TRUTH.md) | Product needs, business rules, architecture, technical contracts, feature/module mapping, accepted decisions |
| [`DATABASE_SCHEMA.md`](DATABASE_SCHEMA.md) | Frozen logical tables, fields, relationships, constraints, and migration dependency order |
| [`IMPLEMENTATION_PLAN_AND_OWNERSHIP.md`](IMPLEMENTATION_PLAN_AND_OWNERSHIP.md) | Rigid two-developer split, file permissions, implementation order, PR gates, acceptance criteria |
| [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) | Verified baseline, implemented scaffold, missing capabilities, evidence required to change status |
| [`LOCAL_RUNBOOK.md`](LOCAL_RUNBOOK.md) | Setup, run, test, diagnose, and reset the project locally |

## Authority order

For a code handoff or claims about what is currently implemented, start with [`PROJECT_HANDOFF.md`](PROJECT_HANDOFF.md). It is an as-built guide and explicitly identifies where older target/design documents are aspirational or stale.

1. `PROJECT_HANDOFF.md` describes current code behavior and limits. It does not silently amend accepted product decisions.
2. `SOURCE_OF_TRUTH.md` governs product needs, business rules, architecture, technical contracts, and accepted decisions.
3. `DATABASE_SCHEMA.md` governs logical table shape, relationships, constraints, and migration dependency order.
4. `IMPLEMENTATION_PLAN_AND_OWNERSHIP.md` governs ownership and workflow; it cannot silently change product/API/database decisions.
5. `IMPLEMENTATION_STATUS.md` reports reality; it does not authorize scope changes.
6. `LOCAL_RUNBOOK.md` explains commands for the current repo; it cannot override architecture or security rules.

If a decision changes, Developer A updates the source of truth and affected plan/status/runbook in the same PR or a coordinated documentation PR. Do not maintain alternate copies of these documents elsewhere.

## Important distinction

The project currently has a working scaffold/demo baseline, not the complete API-testing product. A documented design, route inventory, or planned file is **not** evidence that it has been implemented. See `IMPLEMENTATION_STATUS.md`.

## Deprecation procedure

After the team reviews this set, move the old overlapping documents to a clearly marked `docs/archive/deprecated-2026-10-16/` folder or remove them in a reviewed PR. Do not delete them before confirming this set is committed and both developers have reviewed it. The archive is historical only and must not be treated as normative.
