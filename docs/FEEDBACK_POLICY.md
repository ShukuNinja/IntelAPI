# Feedback policy

The current deterministic policy is `feedback-rules-v1`. It is applied after a candidate run and stored in that run's execution report. It never issues the next HTTP request automatically.

The policy evaluates conditions in this order:

1. A non-HTTP outcome (timeout, connection error, blocked target, or response limit) stops exploration for transport/policy review.
2. Any failed explicit assertion stops exploration for assertion review.
3. A contract observation (undocumented response or supported schema mismatch) stops exploration for human review.
4. An incomplete response-schema analysis stops exploration until the skipped schema is reviewed.
5. A zero proposal budget terminates with `stop_proposal_budget_exhausted`.
6. Otherwise, propose distinct candidate IDs for the operation that have no prior run report in the current project, up to the caller's `follow_up_budget` (0–20).
7. If no such candidate remains, terminate with `stop_no_unseen_candidates`.

Each report includes the selected action, rule version, rationale, proposal budget, proposed IDs, and `automatic_execution: false`. Proposals require explicit user selection in the Explorer. The proposal budget bounds suggestions for one report; it does not impose a campaign-wide request budget or count later manual executions.

This policy is a small implemented workflow slice. Durable campaign state, candidate validation states beyond preview, multi-run audit timelines, per-campaign request budgets, and policy comparisons are not implemented yet. Transport and contract observations are not treated as confirmed defects.
