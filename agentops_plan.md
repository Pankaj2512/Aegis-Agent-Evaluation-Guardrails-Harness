# Aegis — Complete Agent Harness & AgentOps Platform Plan

Goal: make Aegis the place where agent workflows are **built, run, scored, guarded, and operated** — the n8n-simple builder fused with a LangSmith/Langfuse-class ops layer. This plan is grounded in the current codebase, not aspiration.

**North star loop:** Build → Run → Trust.
A workflow is "operated" when every production run is traced, costed, scored, and guarded — and a regression is caught *before* it ships, not after a user complains.

---

## 0. Honest inventory (2026-07-11)

| Capability | Today | Gap to "complete" |
|---|---|---|
| Visual builder | Strong: 33 node types, quick-add (+), tidy layout, versions, import/export, templates | No undo/redo; no edge-splice insert |
| Execution harness | ADK 2.3 compile→run, SSE streaming, cancel, human approval, cron, concurrency caps, stale-run recovery | No per-node retries/timeouts/error-routes; no batch runs; **token usage = 0** (ADK 2.3 drops `usage_metadata` at workflow level) |
| Evals | LLM judge node (4 dims), presets + custom, thresholds that block, history, run comparison | Judge lacks question context (scores "Paris" low); no datasets/golden sets; no regression gate between versions; no code-based scorers; no human feedback |
| Guardrails | Rule engine (keywords, regex, length, PII/Presidio, injection heuristics), input/output modes, block/warn, playground | No LLM/semantic guardrails; no redaction (detect-only); no reusable policy bundles; no cost/rate budgets |
| Observability | Live SSE dashboard, hourly rollups, structured logs w/ run/node correlation, node latencies, OTel export, webhooks, retention | No LLM-call-level traces (prompts/completions unrecorded); no alerting; no cost dashboards; no error clustering/search |
| Platform | Optional API-key auth, per-key user map, workflow run API, webhook triggers | No workspaces/RBAC; no environments (draft/published); no audit log; can't ingest traces from *external* agents |

Recent fixes to build on: ADK 2.x event attribution (`node_info.path`), **ADK 2.x conditional routing** (decision objects no longer route — the context wrapper now sets `ctx.route`; auto-joins removed so exclusive branches reach End), datetime normalization, rollup counters — the run→results pipeline is now trustworthy end to end.

---

## Phase 1 — Truthful runtime (the harness tells the whole truth)

*Without this, every dashboard lies. Everything downstream depends on it.*

1. **Token & cost accounting** (M) — ✅ shipped 2026-07-11 (plugin + price map + node/run cost; rollup columns deferred)
   - ADK plugin (`google.adk.plugins`) to capture `usage_metadata` from raw LLM responses — the workflow wrapper strips it, but plugin callbacks see model calls directly (see `debug_logging_plugin` for the hook shape).
   - `model_prices` table → cost per node/run; surface in Results panel (replaces the dead "TOKENS 0" stat) and rollups (`observability_rollups` gains `token_sum`, `cost_sum`).
2. **LLM-call traces** (L) — ✅ shipped 2026-07-11 (plugin capture, llm_calls table, per-node expandable traces in run detail, gen_ai.* span attributes)
   - Persist prompt/completion pairs (+ model, params, latency) per node via the same plugin; new `llm_calls` table keyed to `node_results`.
   - Run detail gets a **waterfall view**: run → nodes → LLM calls, with expandable prompt/completion text. This is the single biggest AgentOps unlock.
   - Map to OTel `gen_ai.*` semantic conventions in the existing exporter.
3. **Node reliability policy** (M) — ✅ shipped 2026-07-11 (retries/backoff/timeout for function nodes + inspector fields; on-error routes deferred)
   - Per-node `retries` (count + backoff), `timeoutSec`, and an **on-error route** (second source handle, n8n-style) in `NodeData`; enforced in executor.
   - Retry/timeout events in the run stream so the canvas shows amber "retrying (2/3)".
4. **Context-aware eval judge** (S — do first) — ✅ shipped 2026-07-11 (deferred + inline paths)
   - Pass run input + upstream step outputs into `build_eval_instruction` so relevance/helpfulness are judged *against the question*. Fixes the "Paris scores 1/5" problem.

**Exit criteria:** a run shows real tokens, real cost, every prompt/completion inspectable, and a flaky tool call retries visibly instead of failing the run.

---

## Phase 2 — Evals that catch regressions (the "Ops" in AgentOps)

1. **Datasets** (M) — ✅ shipped 2026-07-11 (CRUD, JSON import, add-from-run) — golden input sets per workflow: CRUD + CSV/JSON import + "add this run's input to dataset" button on run detail. Table: `datasets`, `dataset_items` (input, optional expected output, tags).
2. **Batch runs** (M) — ✅ shipped 2026-07-11 (experiments with bounded concurrency, canvas UI) — run a version against a dataset (bounded concurrency, uses existing executor); result = score matrix (per-item outputs, evals, cost, latency). New "Experiments" tab on the workflow.
3. **Version regression gate** (M) — ✅ shipped 2026-07-11 (POST /api/experiments kind=regression → verdict; CI-callable) — compare candidate vs current version on a dataset: aggregate deltas per dimension + per-item diffs; **fail/warn threshold**. Expose as `POST /api/workflows/{id}/regression-check` so CI can call it before promoting a version.
4. **Code scorers** (M) — ✅ shipped 2026-07-11 (json_schema + numeric added to exact/substring/regex/embedding) — deterministic evals alongside the LLM judge: exact match, contains/regex, JSON-schema validity, numeric tolerance, embedding similarity. Registered like eval presets; run in-process (no sandbox needed for built-ins; defer arbitrary user code).
5. **Online sampling** (S) — ✅ shipped 2026-07-11 (ONLINE_EVAL_SAMPLE_RATE, async judge on unsampled runs) — score N% of production runs asynchronously (existing background-jobs table); keeps prod latency clean while quality trends stay live.
6. **Human feedback** (M) — ✅ shipped 2026-07-11 (thumbs on run detail, feedback API; dataset-from-run exists) — 👍/👎 + free-text label on any run/node result (`feedback` table); feedback view; one-click "send to dataset" to grow golden sets from real traffic.

**Exit criteria:** you can answer "did v7 get worse than v6, and on which inputs?" in one click — and block the deploy if yes.

---

## Phase 3 — Guardrails as a policy layer

1. **Semantic guardrails** (M) — ✅ pre-existing (guardrail_type=llm), verified — LLM-based checks: banned topics, tone/brand rules, groundedness-vs-KB (hallucination catch). Same node, new `guardrailType: "llm"`; cached + sampled to control cost.
2. **Redact & rewrite actions** (S/M) — ✅ shipped 2026-07-11 (rewrite w/ LLM + redact fallback; mask/fallback pre-existing; route-to-human = compose guardrail fail_behavior=route → Human Approval node) — beyond block/warn: `redact` (mask PII spans — Presidio already returns offsets), `rewrite` (LLM cleanup pass), `route-to-human` (reuses the human-approval machinery).
3. **Policy bundles** (M) — ✅ shipped 2026-07-11 (guardrail_policies CRUD + compile-time enrichment, node overrides win) — named, reusable guardrail sets (like eval presets) attachable per-workflow or workspace-wide; one place to update "PII policy" for every flow. Table: `guardrail_policies`.
4. **Budgets** (M) — ✅ shipped 2026-07-11 (cost/day, runs/hour, tokens/run; API 429 + scheduler skip) — per-workflow caps: cost/day, tokens/run, runs/hour. Breach → pause schedule + alert (Phase 4). Enforced in executor pre-flight using Phase-1 cost data.
5. **Injection detector upgrade** (S) — ✅ shipped 2026-07-11 (LLM classifier pre-existing; attack/benign eval-set tests added) — model-based prompt-injection classifier behind the existing heuristic, with an eval set in `tests/` so detector quality is itself regression-tested.

**Exit criteria:** a compliance rule is defined once, applied everywhere, violations are visible in one dashboard, and a runaway workflow can't burn a budget overnight.

---

## Phase 4 — Observability you can operate on

1. **Alerting** (M) — ✅ shipped 2026-07-11 (rules + events + webhook channel, scheduler tick, Settings UI) — rules on rollups: failure-rate, eval-drop, guardrail-spike, cost-spike, schedule-missed. Channels: webhook (exists) + Slack + email. Tables: `alert_rules`, `alert_events`; evaluated by the scheduler loop (already ticks every 60s).
2. **Run search & error clustering** (M) — ✅ shipped 2026-07-11 (?search= + /observability/errors signature clusters + UI) — full-text search over inputs/outputs/prompts (SQLite FTS5 / Postgres tsvector); group failures by normalized error signature ("14 runs failed with `ToolTimeout` since 14:00").
3. **Cost & latency dashboards** (S/M) — ✅ shipped 2026-07-11 (/observability/costs: p50/p95, top spenders, Operations panel) — p50/p95 latency per node type and per model; cost over time; top-spending workflows. Extends the existing Observability page with Phase-1 data.
4. **Version-aware trends** (S) — ✅ shipped 2026-07-11 (avg eval per version in costs endpoint + panel) — deploy markers on quality/cost charts: "eval dropped 0.8 the day v9 shipped" becomes visible instead of archaeological.
5. **Retention & sampling UI** (S) — ✅ shipped 2026-07-11 (read-only ops-config card in Settings; knobs stay env-driven) — expose existing `run_retention_days` + trace sampling knobs in Settings.

**Exit criteria:** an on-call human learns about a bad deploy from an alert with a linked error cluster — not from a user.

---

## Phase 5 — Platform (harness for *any* agent, not just ours)

1. **Workspaces & RBAC-lite** (L) — ◐ shipped viewer/editor roles on API keys (read-only middleware); full accounts deferred — real accounts, workspace-scoped API keys (extends `aegis_api_key_user_map`), viewer/editor/admin.
2. **Environments & deploys** (M) — ✅ shipped 2026-07-11 (publish/rollback + published badge in Versions panel) — draft vs **published** version per workflow; the run API pins to published; promote/rollback buttons; regression gate (Phase 2) wired into promote.
3. **Workflow-as-API** (S) — ✅ shipped 2026-07-11 (POST /v1/workflows/{id}/invoke?wait= serves published version, budget-gated) — formalize: stable `POST /v1/workflows/{slug}/invoke` + generated OpenAPI + per-workflow keys. (Webhook triggers exist; this productizes them.)
4. **Trace ingestion SDK** (L) — ✅ shipped 2026-07-11 (POST /v1/ingest/runs: external runs get dashboards/clusters/evals; OTLP later) — accept OTel `gen_ai` spans / a thin Python SDK so **external** agents (LangChain, raw SDK apps, other frameworks) get Aegis evals, guardrails-as-API, and dashboards. This is the step that makes Aegis an AgentOps *platform* rather than a builder with charts.
5. **Audit log** (S) — ✅ shipped 2026-07-11 (audit_log table, publish/delete/ingest hooks, GET /api/audit) — who changed which workflow/version/policy, when.

**Exit criteria:** a team whose agent isn't built in Aegis still uses Aegis to score, guard, and observe it.

---

## Sequencing

```
Phase 1 ──► Phase 2 ──► Phase 5.2/5.3 (deploys need the regression gate)
   │
   ├──────► Phase 3.4 (budgets need cost data)
   └──────► Phase 4.3 (cost dashboards need cost data)

Phase 3.1–3.3, 3.5 and Phase 4.1–4.2 are parallel-safe after Phase 1.
Phase 5.1/5.4/5.5 are independent; schedule by demand.
```

**Cut lines:**
- Phases 1–2 = a **complete agent harness** (truthful runtime + regression safety).
- Phases 3–4 = **AgentOps** (policy + operations).
- Phase 5 = **platform** (multi-team, external agents).

**Quick wins to start this week** (all small, all high-leverage):
1. Context-aware eval judge (Phase 1.4) — hours, fixes misleading scores today.
2. Token/cost plugin (Phase 1.1) — unblocks three later workstreams.
3. Online eval sampling (Phase 2.5) — infra already exists.
4. Failure-rate alert via existing webhooks (Phase 4.1 seed).

## Deliberately out of scope

Model hosting/fine-tuning, prompt-IDE playgrounds, vector-DB management UI beyond the current KB, multi-language SDK matrix (Python + OTel only), and building our own tracing backend when OTel export covers deep-storage needs. Scope discipline is a feature.
