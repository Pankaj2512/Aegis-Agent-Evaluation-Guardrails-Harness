# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What Aegis is

A visual agent-workflow workbench: users compose graph workflows (LLM agents, tools, routers, guardrails, evals) on a React Flow canvas, run them against real inputs via Google ADK + Gemini, and operate them through an observability/triage surface. Two apps in one repo: `backend/` (FastAPI, Python 3.12) and `frontend/` (Next.js 14 App Router, TypeScript).

## Commands

### Backend (from `backend/`, with `.venv` activated)

```bash
pip install -r requirements.txt
alembic upgrade head                          # schema is owned by Alembic
uvicorn app.main:app --reload --port 8000     # dev server

# Tests — SQLite + fake key, no external services needed
DATABASE_URL=sqlite:///./test.db GOOGLE_API_KEY=test-key python -m pytest -q

# Single file / single test
DATABASE_URL=sqlite:///./test.db GOOGLE_API_KEY=test-key python -m pytest tests/test_compiler.py -q
DATABASE_URL=sqlite:///./test.db GOOGLE_API_KEY=test-key python -m pytest -k "test_name" -q

# New migration (revision files are numbered: 001_..., 002_..., keep the sequence)
alembic revision --autogenerate -m "msg" && alembic upgrade head
```

There is no Python linter/formatter configured; match the existing style.

### Frontend (from `frontend/`)

```bash
npm run dev          # http://localhost:3000, needs NEXT_PUBLIC_API_URL in .env.local
npm run typecheck    # tsc --noEmit
npm run lint         # next lint
npm run build
```

There is no frontend test suite; `typecheck` + `lint` + `build` are the gate. CI
(`.github/workflows/ci.yml`) has three jobs: **backend** (`alembic upgrade head` against a fresh
SQLite DB, then pytest), **migrations-postgres** (`alembic upgrade head` against a fresh
`pgvector/pgvector:pg16` service container — SQLite accepts dialect-specific mistakes that Postgres
rejects, so migrations are gated on both), and **frontend** (`typecheck`, `lint`, `build`). Keep all
three green.

### Environment

`cp .env.example .env` at the repo root (backend config loads `.env` from `backend/` or the root via pydantic-settings in `app/config.py`). `GOOGLE_API_KEY` is required for real runs; `DATABASE_URL` defaults to SQLite for local dev, Postgres in production (`docker compose up -d postgres`). Frontend needs `frontend/.env.local` with `NEXT_PUBLIC_API_URL`. Health check: `curl http://127.0.0.1:8000/health`.

## Architecture

### Run pipeline (the core loop)

Workflow graphs are stored as JSON (`nodes` + `edges`) in Postgres. A run flows through:

1. `app/services/graph_validation.py` — validates the DAG (must be Trigger → … → End, acyclic, no orphan edges) before save or compile.
2. `app/services/compiler.py` — `compile_workflow()` translates graph JSON into a Google ADK `Workflow` (agents, join nodes, routed edges). Non-LLM node behaviors come from `_make_*_fn` factories in `app/services/node_handlers.py`.
3. `app/services/executor.py` — executes via the ADK `Runner`, streams node events to SSE subscribers through an in-memory `_RunEventBroker`, applies guardrails/eval thresholds, and records observability rollups.

### Node type system spans both apps

Adding or changing a node type touches a fixed set of files that must stay in sync:

- Backend: `app/services/node_registry.py` (canonical metadata, served to the UI), `node_handlers.py` (execution factory), `compiler.py` (wiring), `graph_validation.py` if it has structural rules.
- Frontend: `src/types/workflow.ts` (`NodeType` union + node data types), `src/lib/node-registry.ts` (labels/icons/categories), and the matching canvas component in `src/components/canvas/nodes/`.

### Schema and migrations

Alembic is the single source of schema truth — the app deliberately does **not** call `Base.metadata.create_all()` on startup; instead `app/services/startup.py` gates boot on the DB being at Alembic head (`migration_check_strict`). Tests are the exception: `tests/conftest.py` builds the schema with `create_all` under SQLite and stamps Alembic head to satisfy the gate. Use the `valid_graph()` helper from conftest to build test graphs that pass Trigger→End validation.

### Execution modes and the single-process constraint

`RUN_EXECUTION_MODE=inline` (default) executes runs in the API process. `worker` mode has a separate `worker.py` process claim and execute runs — the API must not also start the run worker (split-brain double-claim). SSE streams and human-approval waits live in in-memory state in the executor, so in worker mode `/stream` and `/approve` served by the API cannot see them; this is a known constraint, don't "fix" it casually.

### Backend layout

`app/api/*` routers (one per resource: workflows, runs, observability, credentials, guardrail_policies, …) → `app/schemas/*` Pydantic models → `app/services/*` (all business logic, ~60 modules) → `app/db/models.py` (single SQLAlchemy models file). All settings live in `app/config.py` (`Settings`); never read env vars directly. Auth is optional API-key auth (`X-Aegis-API-Key`) with a read-only "viewer" role enforced by middleware in `app/main.py`; rate limits only apply when auth is enabled. Credential secrets are Fernet-encrypted when `APP_ENCRYPTION_KEY` is set, plaintext with a loud warning otherwise.

### Frontend layout

- All backend calls go through the typed client in `src/lib/api.ts` (single `request()` helper, `NEXT_PUBLIC_API_URL` base, auth headers from `src/lib/auth.ts`). Types live in `src/types/workflow.ts`.
- TanStack Query everywhere, with cache keys centralized in `src/lib/query-keys.ts` — add new keys there, don't inline them.
- SSE (run stream, observability stream) is proxied through Next route handlers under `src/app/api/*/stream/route.ts` rather than hitting the backend directly.
- The canvas lives in `src/components/canvas/` (React Flow via `@xyflow/react`): `WorkflowCanvas.tsx` orchestrates; node renderers in `nodes/`, run-mode UI in `run/`, toolbar/status chrome in `chrome/`.
- Stack: Tailwind v3 (not v4), shadcn/Radix primitives in `src/components/ui/`, framer-motion, sonner toasts.

## Conventions

- Commit messages follow conventional-commit style seen in history: `feat(canvas): …`, `fix(ui): …`, `test(mvp2): …`.
- Design language is deliberate: warm near-black surfaces, bone/monochrome chrome, with color reserved for status and data. Match the existing palette and density when touching UI; design specs and phase plans live in `docs/superpowers/`.
- Prefer small, reviewable changes; describe *why*, not only *what* (from the repo's contributing notes).
