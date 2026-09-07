# Aegis Issue Tracker

Last updated: 2026-06-30

## Resolved (Phase 14–16 + Security Hardening + P2/P3)

| Area | Issue | Resolution |
|------|-------|------------|
| Security | Code sandbox breakout via `json.codecs.sys` | `_SafeJsonNamespace` + AST visitor restrictions |
| Security | HTTP SSRF DNS rebinding | DNS pinning in `safe_http_request` |
| Security | Postgres integration SSRF | `_validate_postgres_connection_url` |
| Security | Postgres read-only regex bypass | `SET TRANSACTION READ ONLY` |
| Security | SMTP blocks event loop | `asyncio.to_thread` in email integration |
| Security | SSRF in webhook dispatch | `validate_http_url` + `safe_http_request` in `webhook.py` |
| Security | SSRF in Discord/Slack integrations | URL validation + pinned HTTP in `integrations.py` |
| Security | SQL injection in Postgres node | Template placeholders bound as SQL parameters |
| Security | ReDoS in user-supplied regex | `regex_safety.py` + validation in `guardrail.py` |
| Security | Code sandbox execution timeout | `ThreadPoolExecutor` + 5s timeout in `code_sandbox.py` |
| Security | Templates endpoint unauthenticated | `get_current_user_id` on `GET /api/templates` |
| Security | CORS wildcard credentials | `allow_credentials=False` when using `*` wildcard origin in `main.py` |
| Bugs | Approval race before node wait | Early return from `_approval_results` in `wait_for_approval` |
| Bugs | Sub-workflow infinite recursion | Call stack depth limit + cycle detection |
| Bugs | `has_eval` run filter on SQLite | Python-side filter via `run_filters.py` |
| Bugs | SQLite JSON query filters (`eval_passed`, `guardrail_blocked`) | Python-side filters in `runs.py` |
| Bugs | Embedding dimension mismatch | Hash fallback aligned to 768-dim (pgvector column) |
| Bugs | EventSource connection leak (canvas) | `runSourceRef` + unmount/error cleanup |
| Bugs | Unhandled promise in RunComparison | `.catch()` on `getEvalHistory` |
| Bugs | refreshTimer leak (observability) | `clearTimeout` on unmount |
| Bugs | Stale closure in Save→Run flow | Inline `saveVersion` returns fresh `versionId` |
| Bugs | Stale closure on run cancel | `currentRunIdRef` + memoized `handleStop` |
| Bugs | Backspace deletes while in `<select>` | Exclude `HTMLSelectElement` from delete handler |
| Bugs | Falsy `0` rendered in RunDetailView | Explicit length checks |
| Bugs | Missing create-workflow error toast | `toast.error` in `workflows/new` |
| Bugs | JSON path list index parsing | Supported array/list indices (e.g. `items.0.name`) in JSON Parse node |
| Bugs | HTTP header template rendering | Render templates inside header values to allow dynamic authorization headers |
| Performance | Scheduler scans all workflow graphs | `workflow_schedules` table + indexed query |
| Performance | Scheduler in-memory dedup | `last_fired_at` + `FOR UPDATE SKIP LOCKED` |
| Performance | Long-held DB sessions during runs | Short-lived `_with_run_session` in executor |
| Performance | Observability 100-run scans | Hourly rollups (write + read) |
| Performance | Sync DB in `/health` | `asyncio.to_thread` for DB counts |
| Performance | Persistent SSE on all pages | Lazy connect when first subscriber attaches |
| Performance | Inefficient retention query | Bulk `delete(synchronize_session=False)` |
| Performance | Rollup idempotency on backfill | `reset_rollups_for_user` before rebuild |
| Reliability | Race conditions in schedule claim | Per-schedule isolated `SessionLocal` claims |
| Reliability | SSE subscriber queue leaks | Drop full queues on `QueueFull` in broadcast |
| Ops | KB bulk/reindex blocks API | DB-backed `background_jobs` queue |
| Ops | No job status endpoint | `GET /api/jobs/{id}` |
| Ops | Runs compete with API threads | Optional `RUN_EXECUTION_MODE=worker` + `worker.py` |
| Ops | Deprecated worker lifecycle hooks | FastAPI `lifespan` in `worker.py` |
| Ops | Retention job scheduling | `_maybe_run_retention` in scheduler loop (24h cadence) |
| Product | Version diff in sidebar | `VersionDiffView` wired in `VersionHistory` |
| Product | Workflow version visual diff on canvas | `buildDiffHighlightMap` overlay on nodes |
| Product | Eval regression live alerts | SSE `eval_regression` banner on observability page |
| Product | Human approval template | `human-approval-gate` in `templates.py` |
| Product | No DELETE endpoint for workflows | `DELETE /api/workflows/{id}` with cascade cleanup |
| Product | API key rotation + audit log | `rotateApiKey` + audit UI in settings |
| RAG | pgvector column + vector search | Migration 006 + `vector_search.py` |
| RAG | pgvector index tuning | Migration 007 HNSW index on `embedding_vector` |
| UX | Phase 15 design uplift | Shared primitives, mobile nav, responsive canvas |
| UX | Phase 16 UI/UX polish | Lazy canvas tabs, dynamic RunResultsPanel, relative timestamps, EmptyState gaps |
| UX | Accessibility gaps | Skip link, filter `aria-pressed`, tab roles, `prefers-reduced-motion` |
| UX | Canvas mobile toolbar crowding | Stacked header layout + scrollable action bar |
| UX | EvalScoresChart off-palette colors | Design tokens for radar chart and deltas |
| UX | Broken `section-title` class | Fixed to `section-heading` in RunDetailView |
| Performance | Canvas sidebar idle queries | Mount only active sidebar tab panel |
| Performance | Dashboard duplicate state sync | React Query source of truth + cache invalidation |
| Performance | VirtualList unstable keys | `getItemKey` for observability run rows |
| Architecture | SPA mutable cache conflicts | Removed module-level caches from `api.ts` |
| Reliability | Unbound rate limiter memory | Periodic prune of stale bucket keys |
| Reliability | Fire-and-forget task leaks | `schedule_task` with exception logging |
| Code Quality | Duplicate `needs_gemini` helper | `workflow_capabilities.py` shared module |

## Open / Backlog

### P2 — Medium Priority

| Area | Issue | Location / Context | Notes |
|------|-------|--------------------|-------|
| Scale | Redis-backed queue | *New design needed* | DB queue works for single-region; Redis for multi-worker scale out |

## Reporting

Open new issues on GitHub with reproduction steps, expected behavior, and environment (`DATABASE_URL` dialect, `RUN_EXECUTION_MODE`, auth settings).