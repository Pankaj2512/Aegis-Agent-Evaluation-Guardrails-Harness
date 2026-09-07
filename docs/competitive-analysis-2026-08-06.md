# Competitive analysis — Aegis vs. the market

**Date:** 2026-08-06 · **Method:** 12 parallel web-research agents (≥5 primary sources each: official docs, changelogs, pricing, GitHub releases, 2025–26 comparisons) + 3 codebase-inventory agents (backend surface, frontend surface, known-issues backlog), with contested claims re-verified against source. Every "missing" claim below was checked against the Aegis codebase with file evidence.

**Platforms researched:** Dify, n8n, Lyzr AI, Langflow, Flowise, Zapier (Agents/MCP/Canvas), Make.com, Vellum, CrewAI (OSS + AMP), Relevance AI, VectorShift, Stack AI, and the trust-layer benchmark pair LangSmith + Langfuse.

---

## 1. The strategic read

Aegis has built **the trust layer of LangSmith on top of a canvas like Dify's** — and that combination is genuinely rare. Evals (datasets, experiments, CI gates, online sampling, LLM-judge + deterministic + RAG metrics), guardrails (Presidio PII, injection, moderation, structured-output repair, reusable policies, workflow-level plugin enforcement, a playground), and observability (span waterfalls, LLM-call logs, cost dashboards, anomaly alerts, OTel export, Trust dashboard) all in one self-hosted product. Dify has **no native eval framework at all**; Zapier, Make, Langflow, and VectorShift have essentially none; Flowise and n8n paywall theirs.

The gaps are concentrated in the **engine room**, not the ops surface: Gemini-only models, no agent tool-calling loop, no loops/iteration, no MCP in either direction (in protocol terms), no chat surface, no streaming, paste-text-only RAG, and 4 integrations. In 2026 these are commodity table stakes that every one of the 12 researched platforms ships. The trust layer is the differentiator; the engine room is the entry ticket.

### Where Aegis is already ahead or at par (don't break these)

| Area | Aegis today | Market position |
|---|---|---|
| Eval framework | Datasets, batch + regression experiments vs. baseline, CI gate endpoint, online sampling, judge + 6 deterministic scorers, RAG triad, rubric editor w/ live preview | Ahead of Dify/Zapier/Make/Langflow/VectorShift (none); ahead of Flowise/n8n (paywalled/lighter); approaching LangSmith/Langfuse |
| Guardrails | Rules + Presidio + injection classifier + moderation thresholds + structured-output w/ LLM repair + policies + templates + playground + workflow-level ADK plugin | Among the deepest anywhere; only Lyzr positions harder here. n8n/Zapier only added guardrail nodes in late 2025/2026 |
| Observability | Nested span waterfall, per-LLM-call prompt/completion/cost, p50/95/99, failure clusters, sessions, anomaly + baseline alerts, OTel export, SSE live stream, Trust dashboard | At par with the specialist tools' core loop, and none of them have an authoring canvas |
| AI copilot | NL→workflow, reviewable graph edits, node suggestions, explain-run, variant compare, schema gen | On-trend (Dify Cmd+K, n8n Builder, Maia, Zapier Copilot, Langflow Assistant) — Aegis's reviewable-diff approach is tasteful |
| Craft | 310 backend tests, security-hardening record, design system, 313 aria attrs, reduced-motion, dark/light | Ahead of most OSS competitors (cf. Langflow's 3 RCE CVEs, Flowise's patch tail, CrewAI's 5 CVEs) |

---

## 2. Missing features (prioritized)

### P0 — adoption blockers; every serious competitor has them

| # | Missing feature | Who has it | Aegis reality (verified) |
|---|---|---|---|
| 1 | **Multi-model / multi-provider support** — per-node model+params, BYO keys, local models (Ollama), incl. judges/guardrails/embeddings | **All 12.** Dify: hundreds via plugins; n8n: 18+ providers; Flowise 30+; CrewAI 30+; Vellum 23; Lyzr 7; Langflow, Relevance, VectorShift, Stack AI multi; even Zapier does BYOM | Gemini-only everywhere (exec, judge, guardrail, embeddings, assist). `model_ref.py` is an unwired seam that silently falls back to Gemini. No model/temperature field in the UI at all. Already ROADMAP P0 — confirmed the single most disqualifying gap |
| 2 | **Agent-native tool calling (ReAct/function-calling loop)** — tools attached *to* the agent, agent decides when to call | All 12 — this is what "agent" means in 2026 (Dify agent node, n8n AI Agent, Flowise Agentflow, Langflow Tool Mode, Vellum Agent Node, CrewAI crews, Make/Zapier agents…) | Aegis "agents" are instruction-only single-shot LLM calls; tools are separate graph nodes the user wires manually. No tools param, no loop (`compiler.py _build_adk_node`). The biggest credibility gap for an "agent workbench" |
| 3 | **MCP — client AND real server** | Two-way: Dify, n8n (deepest: client node + per-workflow server + instance server), Langflow (every project is an MCP server), Flowise, Make, Zapier, Stack AI, Relevance. Client: CrewAI, Vellum, Lyzr, VectorShift | No MCP client (workflows can't consume external MCP tools — ROADMAP P0). "MCP server" is a static JSON tool-descriptor from `deploy_descriptor.py`; no endpoint speaks the protocol. MCP client is also the cheapest path to integration breadth (Zapier MCP alone = 8,000 apps) |
| 4 | **Loops / iteration / map-over-list** | Dify (Iteration w/ parallel mode + Loop w/ exit conditions), n8n (Loop Over Items), Flowise (Loop + Iteration), Langflow (Loop), Make (iterators), Vellum (Map node, concurrent), Relevance (foreach), Stack AI (Loop Subflow), Lyzr (loop node) | `graph_validation.py` hard-rejects cycles; no iteration construct of any kind. A real authoring ceiling — "for each row/doc/item" is the most common automation shape |
| 5 | **Chat as a product surface** — multi-turn conversation memory + hosted app page + embeddable widget | Dify (Chatflow + webapp + widget + SSE), Flowise (widget + share links), Langflow (Playground + widget + public links), n8n (chat trigger + @n8n/chat), Lyzr (chat API + widget), Relevance, VectorShift (4 interface types), Stack AI, Zapier Chatbots | `session_id` is an observability grouping tag only — executor creates a fresh ADK session per run, **no prior-turn context ever reaches the model**. No hosted page, no widget (Deploy sheet's "Embed" iframes a POST endpoint with no UI behind it). You cannot *talk to* anything you build |
| 6 | **Streaming responses** — token-level SSE to API consumers and in-builder | Dify, Flowise, Langflow, Vellum, Lyzr, Relevance (SDK streaming incl. thinking tokens), CrewAI, LangSmith deployments | SSE carries node-level events only; `/v1/invoke` is fire-and-poll (90s cap). No model-token streaming anywhere |

### P1 — expected by platform buyers; absence is conspicuous

| # | Missing feature | Who has it | Aegis reality |
|---|---|---|---|
| 7 | **RAG depth**: file upload/parsing (PDF/DOCX), chunking strategies, hybrid retrieval, rerankers, external vector stores, citations | Dify Knowledge Pipeline (visual RAG ETL, parent-child chunking, multimodal), Flowise Document Stores (100+ loaders, 20+ stores, rerankers), n8n (11+ vector stores), Lyzr (KG + text-to-SQL), Vellum (doc indexes + Ragas), VectorShift (live-synced KBs) | Paste-text only (no `UploadFile` anywhere), one embedding per whole doc (no chunking), Gemini embeddings w/ hashing fallback, optional pgvector, no external store connectors, no reranking |
| 8 | **Integration breadth strategy** — OAuth connector framework or aggregator | n8n 1,500+, Zapier 9,000+, Make 3,000+, Relevance 2,000+, Stack AI 70+ enterprise systems, Vellum ~70 + Composio 250+, Lyzr Composio 30+ | 4 integrations (Slack/Discord incoming-webhook, SMTP, read-only Postgres) + 3 search providers. ROADMAP path (MCP + OpenAPI tool import + a few OAuth connectors) is right — but it's blocked on #3 |
| 9 | **Durable execution** — checkpoint/resume, exactly-once, restart-surviving runs | Lyzr SuperFlow (exactly-once, restart-surviving), CrewAI Flows (@persist, resume, fork), n8n queue mode + Redis, LangSmith Deployment, Temporal-class expectations | In-process asyncio; crash loses the run (orphan sweeper just marks failed); worker mode breaks `/stream` + `/approve` (in-memory broker). ROADMAP P1 — confirmed |
| 10 | **Event-source triggers** — email, Slack/Teams, app events; multiple schedules; webhook signing | Dify trigger plugins, n8n (hundreds of app triggers + IMAP + forms), Make mailhooks, Zapier, Relevance (Gmail/Teams/WhatsApp/LinkedIn/calendar), CrewAI AMP (10 types), Stack AI | Manual, inbound HTTP `/trigger`, cron (one schedule per workflow, unique constraint). No event sources, no per-webhook signing secrets |
| 11 | **Human annotation queues + feedback→dataset loop** | LangSmith (queues w/ rubrics, thread items, CRUD API), Langfuse (queues per plan), Lyzr (scenario sim), Relevance (eval checks) | Thumbs+comment per run only; no queue, no labeling workflow, no aggregate feedback analytics. The natural next brick in the trust layer |
| 12 | **Prompt management** — registry, versioning, standalone playground | LangSmith (commit-hash versioning + Context Hub + multi-provider playground), Langfuse (labels + zero-latency caching + playground), Vellum (Prompt Sandbox), Dify (Prompt IDE) | Prompts live inside node JSON; variant-compare is buried in NodeInspector, single-model, ephemeral. No registry, no playground page |
| 13 | **Multimodal I/O** — file/image/audio inputs to workflows and agents | Make (native PDFs/images/CSVs/audio), Vellum (image/doc/video I/O), Dify (multimodal KB + vision), Flowise (vision + chat-time uploads), Zapier (100MB knowledge files), Stack AI (audio/image nodes) | Text-only end-to-end |
| 14 | **Code node depth** — JS, package imports, realistic limits | n8n (JS+Python task runners, npm), Zapier (JS+Python, npm/PyPI, 2min Enterprise), Flowise (server-side JS + deps allowlist), Stack AI, E2B/Modal-style sandboxes (CrewAI, Dify sandboxed Linux agent) | Python-only, 4,000-char cap, zero imports, 5s best-effort timeout |
| 15 | **Per-node error routing** — fail branches / error workflows | n8n (error branch + Error Trigger workflows + autoreplay), Dify (fail-branch + retry), Make (5 error directives), Zapier (error paths) | Verified: retries/backoff/timeoutSec exist per node; error *branches* don't (deferred in agentops_plan) |
| 16 | **LLM caching + model fallback/routing** | Flowise (Redis/in-memory cache nodes), Vellum (prompt caching + fallback patterns), Relevance (auto fallback), CrewAI (tool caching), LangSmith Gateway (spend policies) | No response/semantic cache (compile + assist caches only); no fallback (single provider anyway) |

### P2 — competitive edge / deliberate scope calls worth restating

| # | Missing feature | Who has it | Note |
|---|---|---|---|
| 17 | Multi-agent orchestration patterns (supervisor, crews, handoffs, A2A) | CrewAI (the category), Flowise supervisor/worker, Relevance Workforces, LangSmith Fleet, Langflow agents-as-tools + A2A, Lyzr Manager Agent | Only `sub_workflow` today. ROADMAP P2 — reasonable to defer until #2 lands (agent-tool loop is the prerequisite) |
| 18 | Data tables / durable KV+tabular stores | Zapier Tables, Make data stores, n8n Data Tables, VectorShift Tables | `memory_store/retrieve` + persistent KV only. ROADMAP P2 |
| 19 | Accounts, RBAC, SSO, workspaces, per-user quotas | All commercial platforms (paywalled in most OSS ones too) | Deliberately out of scope (solo product) — but per-webhook signing secrets and per-deployment API keys are the minimum slice worth doing anyway |
| 20 | Environments (dev/staging/prod) + release reviews | Vellum (flagship: env-scoped keys, protected release tags, review approvals), n8n git-based envs, Langfuse env dimension | Aegis has published-vs-latest only; the "review" lifecycle column has no workflow behind it |
| 21 | Plugin/template marketplace & community ecosystem | Dify Marketplace (7 plugin types), n8n community nodes (600+ packages), Flowise marketplace, Relevance | Deprioritized in ROADMAP — right call for now |
| 22 | Voice agents / telephony | Lyzr (Realtime + pipeline, Twilio), Relevance (phone + meeting agents), VectorShift voicebots | Emerging differentiator, not table stakes for Aegis positioning |
| 23 | Browser / computer use | Relevance (Airtop), Stack AI Computer (sandbox + browser replay), Zapier agent browsing, Dify sandboxed Linux agent | Watch; don't chase yet |
| 24 | SDKs + CLI + git sync | n8n (CLI + git envs), Vellum (bidirectional SDK↔canvas sync — its flagship), Langflow lfx, difyctl, CrewAI (git-native) | Aegis: JSON import/export + FastAPI OpenAPI only. A thin Python/TS client SDK would meaningfully strengthen the workflow-as-API story |
| 25 | Inbound OTLP ingestion | LangSmith (OTel ingestion), Langfuse (OTel-native) | `/v1/ingest/runs` is bespoke JSON; docstring says "OTLP later" |
| 26 | Alert channels beyond webhook | LangSmith (PagerDuty/Dynatrace), Langfuse (Slack/webhook/GH Actions), Zapier/Make (email) | `alerts.py` dispatches to `channel_url` webhook only |

---

## 3. Existing features that need polishing / fixing

### Fix — correctness, safety, and trust holes

1. **Guardrails silently pass when `GOOGLE_API_KEY` is missing** (warning-only). A safety feature that no-ops is worse than none — needs a fail-closed mode. `guardrail.py`
2. **Worker mode breaks `/stream` and `/approve`** (in-memory `_RunEventBroker` + approval waits). Documented, but it nullifies the only scale-out story; Redis pub/sub or DB-backed waits is the fix. `executor.py`
3. **Credentials stored plaintext when `APP_ENCRYPTION_KEY` unset** (loud warning). Generate a key on first boot instead of warning. `crypto.py`
4. **Cost dashboards priced from a hardcoded Gemini price table** — silently wrong the day prices change; needs an updatable price catalog (and multi-provider pricing once #1 lands). `token_tracker.py`
5. **Online eval sampling defaults to 0.0** — a headline trust feature ships dark. Default on at a low rate, or nudge in UI. `config.py`
6. **Eval judge on the run critical path** — inline judging adds user-facing latency; move fully async/post-run (partially mitigated today). `upgrade_plan.md` High
7. **Live-run canvas shows incomplete state for instant nodes** (streamed `nodeRunResults` misses trigger/input_schema; replay is complete). Fall back to `run.node_results` in `displayNodes`. `WorkflowCanvas.tsx`
8. **Expanded trace/deck ordering is observed-start, not execution order** — can list LLM Agent before Trigger. `RunDeck.resolveSteps`
9. **Deploy sheet "Embed" tab iframes a POST endpoint with no UI behind it** — actively misleading; remove the tab or build the hosted page (pairs with P0 #5). `DeploySheet.tsx`
10. **Trigger webhooks authenticated with the user's own API key** — no per-webhook signing secrets; a leaked trigger URL is a leaked account key. `workflows.py /trigger`

### Polish — features that exist but are thin vs. the market

11. **Knowledge base**: add file upload + parsing, chunking controls, ≥1 external vector store, citations in outputs (today: paste-text, whole-doc embeddings) — the P1 #7 gap starts as polish here
12. **Code node**: raise the 4,000-char/5s/no-imports limits; add JS; consider an external sandbox (E2B-style) for anything real
13. **Integrations**: Slack/Discord are webhook-only (no OAuth); Postgres is SELECT-only with a 50-row cap; email degrades to log-only without SMTP
14. **Human approval**: no assignee, no notification routing (nobody gets pinged — approvals sit invisible until someone looks); plus the in-memory wait constraint (#2)
15. **Sub-workflow I/O**: input is a single rendered text template — needs structured input/output mapping
16. **Variant compare** → promote out of NodeInspector into a real playground page; persist results as experiments; cross-model once #1 lands
17. **Datasets**: CSV import missing (verified — JSON + capture-from-run only); no item-level editing grid; no golden-answer diff in experiment results
18. **Feedback**: no aggregate analytics view; no path from thumbs → dataset item
19. **Alert rules**: single webhook URL channel; no Slack/email (planned, unshipped)
20. **Observability rollups**: token/cost sums deferred — hourly rollups can't drive cost trend charts directly
21. **Schedules**: one per workflow (unique constraint); no visual builder for multiple/complex schedules
22. **Publish lifecycle "review" column**: status-only — no reviewer assignment or diff-based approval behind it (cf. Vellum release reviews)
23. **Templates**: instance-local only; no import from a shared/community source
24. **OTel**: export-only; `/v1/ingest/runs` bespoke JSON (inbound OTLP planned)
25. **Settings ops-config card**: retention/sampling knobs read-only (env-driven) — make them editable
26. **Budgets**: per-workflow only; no per-consumer/per-key quotas on the invoke API
27. **Canvas QoL**: edge-splice insert missing (can't drop a node onto an edge); NodeInspector.tsx (105KB) and WorkflowCanvas.tsx (104KB) are god-files flagged by the dependency graph — decompose before they calcify
28. **Mobile**: layout-locked canvas shipped, but no mobile nav for the rail; PWA manifest exists unused

### Stale-claim corrections made during verification

- ~~"No undo/redo on canvas"~~ (agentops_plan) — **exists**: `useGraphHistory.ts`, 14 record() sites, ⌘Z wired.
- "Datasets support CSV import" (inventory overclaim) — **does not exist**; JSON + capture-from-run only.
- Per-node reliability: retries/backoff/timeout **do** exist (`retryDelaySec`, `timeoutSec`, `node_llm_*` config); only error *branches* are missing.

---

## 4. Suggested sequencing (if the ROADMAP gets revised)

1. **Multi-model** (P0 #1) — unblocks per-node models, judge/guardrail model dropdowns (seams already read the fields), cross-model compare, honest cost accounting. Biggest single unlock; everything else composes with it.
2. **Agent tool-calling loop** (P0 #2) + **MCP client** (P0 #3a) together — tools-on-agents and MCP-tools-as-agent-tools are one design. Instantly converts the 4-integration story into "any MCP server."
3. **Loops/iteration** (P0 #4) — one `iteration` node (map-over-list with parallel option + max-iterations) covers 80% of demand without giving up DAG validation guarantees.
4. **Chat surface + streaming** (P0 #5–6) — session memory injection, token SSE on `/invoke`, one hosted chat page + widget. This is what makes published workflows *demoable*.
5. **True MCP server** (P0 #3b) — speak the protocol on `/v1`; the descriptor already exists.
6. Then P1 in roughly: RAG ingestion depth → annotation queue (extends the trust-layer lead) → event triggers → durable execution → error branches → prompt playground.

Quick wins worth doing anytime (small, high leverage): fail-closed guardrails, online-eval default, webhook signing secrets, dataset CSV import, alert Slack channel, approval notifications, edge-splice, embed-tab fix.
