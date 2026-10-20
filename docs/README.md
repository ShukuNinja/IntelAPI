# IntelAPI â€” Canonical Development Documentation

**Documentation refresh:** 2026-10-19
**Status:** product/architecture documents describe the accepted target; `IMPLEMENTATION_STATUS.md` and `M0_BASELINE_AUDIT.md` describe the audited source snapshot and known verification limits.

| Document | Authority |
|---|---|
| [`SOURCE_OF_TRUTH.md`](SOURCE_OF_TRUTH.md) | Product needs, business rules, architecture, and accepted decisions |
| [`DATABASE_SCHEMA.md`](DATABASE_SCHEMA.md) | Logical tables, relationships, constraints, and migration dependency order |
| [`IMPLEMENTATION_PLAN_AND_OWNERSHIP.md`](IMPLEMENTATION_PLAN_AND_OWNERSHIP.md) | Ownership, implementation order, and workflow |
| [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) | Current observed implementation status and evidence requirements |
| [`LOCAL_RUNBOOK.md`](LOCAL_RUNBOOK.md) | Setup, run, test, diagnose, and reset instructions |
| [`M0_BASELINE_AUDIT.md`](M0_BASELINE_AUDIT.md) | M0 source inventory, identified gaps, decisions, and verification checklist |

## Authority order

1. `SOURCE_OF_TRUTH.md` governs product needs, business rules, architecture, and cross-cutting decisions.
2. `DATABASE_SCHEMA.md` governs logical schema and migration order.
3. `IMPLEMENTATION_PLAN_AND_OWNERSHIP.md` governs ownership and workflow.
4. `IMPLEMENTATION_STATUS.md` reports implementation reality; it does not authorize scope changes.
5. `LOCAL_RUNBOOK.md` gives operational commands and cannot override architecture/security rules.
6. `M0_BASELINE_AUDIT.md` records observations and verification boundaries for the audited snapshot; it does not replace the source of truth.

A documented endpoint, table, module, or feature is not evidence of implementation. When code and target documentation disagree, record the discrepancy and plan a reviewed change. Do not infer that code is correct merely because it exists.
