# Implementation status

## Stage 1 — Frontend foundation
User-reported acceptance checks passed in their Windows environment. UI remains demo-backed and does not execute target requests.

## Stage 2 — Backend scaffold and CI
Scaffold includes FastAPI, versioned metadata route, liveness/readiness endpoints, centralized settings/logging, SQLAlchemy engine/session, empty Alembic baseline, domain module responsibility notes, Docker Compose, and GitHub Actions.

## Not implemented
Google sign-in/application sessions, domain tables, target HTTP execution and SSRF controls, OpenAPI persistence, durable campaign worker, test generation, analysis, adaptive selection, findings persistence, and reports.
