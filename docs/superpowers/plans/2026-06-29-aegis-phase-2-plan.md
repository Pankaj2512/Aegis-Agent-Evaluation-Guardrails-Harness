# Aegis Phase 2 Improvement Plan

> **For agentic workers:** Use subagent-driven-development or executing-plans to implement task-by-task.

**Goal:** Harden MVP1 into a reliable daily-use platform, then add high-impact workflow and evaluation features that differentiate Aegis from generic agent builders.

**Architecture:** Three incremental releases — Stabilize (1.5), Productize (2.0), Scale (2.5). Each release ships independently testable value. Execution layer stays Google ADK + Gemini; improvements focus on observability, graph fidelity, and eval/guardrail depth.

**Tech Stack:** Next.js 14, FastAPI, Neon PostgreSQL, Google ADK 2.0, Gemini API, React Flow, Alembic, Vitest/Pytest

---

## Current State (MVP1)

**Working:**
- Visual canvas, save/load/versioning
- ADK workflow compilation + execution
- Dashboard, SSE progress, results panel
- Gemini + EXA + DuckDuckGo search options
- Neon PostgreSQL

**Known gaps:**
- Node progress mapping relies on fragile author-name heuristics
- Background runs use `asyncio.run()` in thread pool
- No Alembic migrations, no automated tests
- No run detail page, no error toasts
- Linear DAG only (no branching UI)
- No auth, no deployment pipeline
- No git commits yet

---

## Release 1.5 — Stabilize (1 week)

*Make MVP1 trustworthy for real use.*

### 1.5.1 Execution Reliability
**Files:** `backend/app/services/executor.py`, `backend/app/api/runs.py`

- [ ] Replace `BackgroundTasks` + `asyncio.run()` with native async task (`asyncio.create_task`) on FastAPI lifespan
- [ ] Tag ADK nodes with explicit `node_id` metadata; map events by `node_id` not author string
- [ ] Normalize all outputs via `_stringify_value` (done partially — extend to eval/guardrail JSON)
- [ ] Fail fast when `GOOGLE_API_KEY` missing; return 400 with clear message
- [ ] Add run timeout (e.g. 5 min) and cancellation endpoint `DELETE /api/runs/{id}`

### 1.5.2 Database & DevOps
**Files:** `backend/alembic/`, `backend/app/db/`

- [ ] Add Alembic; generate initial migration from current models
- [ ] Remove SQLite artifact (`backend/aegis.db`) from active path; Neon-only in prod
- [ ] Initial git commit + `.env` safety check in README

### 1.5.3 UX Polish
**Files:** `frontend/src/components/canvas/WorkflowCanvas.tsx`, `frontend/src/app/runs/[id]/page.tsx`

- [ ] Toast notifications for save/run/errors (sonner or shadcn toast)
- [ ] Run detail page: `/runs/[id]` with full node timeline
- [ ] Highlight active node on canvas during SSE stream
- [ ] Loading states on Run / Save buttons

### 1.5.4 Test Coverage (minimum)
**Files:** `backend/tests/`, `frontend/__tests__/`

- [ ] `test_compiler.py` — topological sort, node type mapping
- [ ] `test_search.py` — DuckDuckGo + EXA mock responses
- [ ] `test_api_workflows.py` — CRUD smoke tests against test DB
- [ ] Frontend: API client unit test

**Exit criteria:** Run a 4-node workflow (Agent → Search → Eval → Guardrail) end-to-end with correct per-node results in UI.

---

## Release 2.0 — Productize (2–3 weeks)

*Differentiate on evaluation + guardrails.*

### 2.0.1 Evaluation Suite
**Files:** `backend/app/services/nodes/eval_node.py`, `frontend/src/components/results/EvalScoresChart.tsx`

- [ ] Expand eval schema: faithfulness, helpfulness, relevance, toxicity (1–5 each)
- [ ] Eval presets: "RAG quality", "Support tone", "Code safety"
- [ ] Aggregate run score (weighted average) stored in `metrics_json`
- [ ] Radar chart or scorecard in results panel
- [ ] Eval history: compare scores across runs for same workflow

### 2.0.2 Guardrail Engine
**Files:** `backend/app/services/nodes/guardrail_node.py`

- [ ] Guardrail types: keyword blocklist, regex, max length, PII regex (email/phone)
- [ ] Input vs output mode (validate before/after agent)
- [ ] Fail behavior: `block` (stop workflow) vs `warn` (continue, flag)
- [ ] Guardrail badge on canvas edges when failed

### 2.0.3 Workflow Templates
**Files:** `frontend/src/app/templates/`, `backend/app/api/templates.py`

- [ ] Ship 3 starter templates:
  - Research Agent (Search → Agent → Eval)
  - Calculator Chain (Agent → Calculator → Guardrail)
  - Support Bot (Guardrail → Agent → Eval)
- [ ] "Duplicate workflow" action on dashboard

### 2.0.4 Version Diff & Run Comparison
**Files:** `frontend/src/components/dashboard/VersionHistory.tsx`

- [ ] Version list sidebar on canvas with timestamps
- [ ] Side-by-side run comparison (same input, two versions)
- [ ] Delta on eval scores between versions

**Exit criteria:** User can pick a template, customize guardrails, run twice, and compare eval scores between versions.

---

## Release 2.5 — Scale (3–4 weeks)

*Production-ready platform.*

### 2.5.1 Graph Execution (ADK-native)
**Files:** `backend/app/services/compiler.py`, `frontend/src/components/canvas/`

- [ ] Support conditional branching (router node) on canvas
- [ ] Fan-out / parallel nodes (ADK JoinNode)
- [ ] Validate graph on save (no cycles, single START path)
- [ ] Compile React Flow → full ADK `Workflow` edges (not just linear chain)

### 2.5.2 Auth & Multi-tenancy
**Files:** `backend/app/auth/`, `frontend/src/middleware.ts`

- [ ] Clerk or Auth0 integration
- [ ] `user_id` on workflows and runs
- [ ] Row-level isolation in API queries

### 2.5.3 Deployment
- [ ] Frontend → Vercel
- [ ] Backend → Railway / Fly.io / Cloud Run
- [ ] Neon production branch + env separation
- [ ] GitHub Actions: lint, test, deploy on merge

### 2.5.4 Observability
- [ ] Structured logging (run_id, workflow_id, node_id)
- [ ] Run export (JSON download)
- [ ] Optional webhook on run completion

**Exit criteria:** Deployed URL, authenticated user can create/run workflows, logs traceable by run ID.

---

## Recommended Priority Order

```
Week 1   → Release 1.5 (stabilize)     ← START HERE
Week 2-3 → Release 2.0 eval/guardrails
Week 4-6 → Release 2.5 scale
```

## What NOT to build yet

- A/B testing infrastructure
- One-click agent deployment to production
- Complex memory / RAG ingestion pipelines
- Multi-user real-time collaboration

---

## Immediate Next Session (Day 1)

1. Git init commit
2. Alembic setup + Neon migration
3. Fix async executor (remove thread-pool `asyncio.run`)
4. Run detail page + error toasts
5. E2E test: 4-node workflow

Estimated effort: **4–6 hours** for Day 1 tasks.