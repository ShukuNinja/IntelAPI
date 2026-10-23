# Development rules

- This repository is a modular monolith: React/Vite frontend, FastAPI backend, PostgreSQL persistence.
- Treat `docs/SOURCE_OF_TRUTH.md`, `docs/api_contracts.md`, `docs/DATABASE_SCHEMA.md`, and `docs/IMPLEMENTATION_PLAN_AND_OWNERSHIP.md` as project guidance, not proof that a feature exists.
- Keep remote target access behind one security-reviewed execution boundary. Do not fetch remote URLs or external `$ref`s from parser code.
- Candidate generation, validation, selection, scoring, and diagnosis must be deterministic; optional LLM use is limited to intent routing.
- Never commit `.env`, real credentials, tokens, private user data, generated local databases, or build outputs. Keep `.env.example` as placeholders.
- Verify only checks actually run and record missing capabilities honestly in `docs/BUILD_STATUS.md`.
- Keep feature work on `final-version`; do not merge it into `main` unless the user explicitly requests a merge.
