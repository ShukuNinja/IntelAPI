# API Intelligence Platform — Frontend Foundation

Stage 1 frontend scaffold using React, Vite, TypeScript, React Router, Tailwind CSS, TanStack Query, and Lucide icons.

## Requirements
- Node.js 20.19+ or 22.12+
- npm 10+ (or a compatible package manager)

## Run on Windows PowerShell

```powershell
# 1. Extract this archive, then enter the project folder
cd api-intelligence-platform

# 2. Install dependencies
npm install

# 3. Start the Vite development server
npm run dev
```

Open the URL printed by Vite (normally http://127.0.0.1:5173).

## Validation

```powershell
npm run typecheck
npm run lint
npm run build
```

## What is implemented
- Responsive application shell and sidebar navigation.
- Six primary destinations: Overview, API Workspace, Health Checks, API Explorer, Test Campaigns, Findings & Evidence.
- Collections, Environments, Request History, and Settings supporting routes.
- Reusable buttons, panels, status pills, metrics, page headers, tables, tabs, and empty/loading states.
- Explicit local demo data and mock services; no API calls are sent to external systems.
- Request workspace interactions are local UI state only. The Send button deliberately does not execute HTTP requests until the backend execution service is implemented.
- TanStack Query is configured at the app root for subsequent server-state integration.

## Architecture notes
- `src/app`: routing and application providers.
- `src/components`: shared shell and reusable UI.
- `src/features`: page-level feature modules.
- `src/lib`: API client and mock service boundaries.
- `src/styles`: design tokens and global styles.

## Important
This is a frontend foundation, not a completed API tester. All data currently shown is demo data. Do not treat demo health status or findings as observations about real target APIs.

The existing project decision documents should be placed in `docs/` before implementation expands:
- `SOURCE_OF_TRUTH.md`
- `TECHNICAL_DESIGN.md`
- `API_CONTRACT.md`
- `DATABASE_DESIGN.md`
- `DEVELOPMENT_WORKFLOW.md`
