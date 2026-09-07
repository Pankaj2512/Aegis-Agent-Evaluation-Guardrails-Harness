# Aegis — Future Roadmap (Feature Gaps)

> **Source of truth:** derived from a mid-2026 competitive analysis of visual AI-agent
> workflow builders (n8n, Zapier, Make, Vellum, Dify, Langflow, LangGraph) cross-referenced
> against a codebase audit of Aegis. Full research report:
> `~/Documents/Visual_AI_Agent_Builders_Research_20260723/` (Markdown/HTML/PDF).
>
> **Last updated:** 2026-07-24. Re-verify competitor facts before acting — this market moves monthly.

## Framing

Aegis is already on the category's *defensible ground*: a premium glass-box run experience
(run lens, live + replay trace, per-node telemetry, waterfall), evaluation (presets, scores,
datasets, experiments), guardrails, publish/deploy (cURL/embed/MCP-spec + invoke API),
observability + cost dashboards + alerts, templates, version lifecycle, memory nodes,
`kb_retrieve` RAG, `human_approval` HITL, `sub_workflow` composition, a real integration set
(slack/discord/email/postgres/google/http/search), a scheduler, encrypted credentials, and it is
self-hostable. The competitive conclusion: the durable differentiators are the *quality of the
run/trace/eval experience, authoring depth, ship-to-prod, and deployment sovereignty* — which
Aegis already has a credible v1 of. This roadmap therefore focuses on **parity gaps that a savvy
evaluator would notice in the first five minutes**, not on chasing commoditized breadth.

Priority key: **P0** = table-stakes the app conspicuously lacks; **P1** = depth gaps vs the leaders;
**P2** = minor / opportunistic.

---

## P0 — Table-stakes gaps (highest leverage)

### P0.1 · Multi-model / multi-provider support
- **Gap:** Aegis is **Gemini-only** — `google.adk` runtime, `gemini-2.5-flash` +
  `text-embedding-004`, no OpenAI/Anthropic/Claude, no local models (Ollama).
- **Why it matters:** every one of the seven competitors is multi-provider; n8n, Dify, and
  LangGraph add local/self-host models for privacy. Single-vendor lock-in is the most-expected
  feature the app lacks, and it undercuts Compare mode (today you can compare prompts/params but
  not *providers*), the "side-by-side model comparison" story Vellum/Zapier market, and
  data-sovereignty positioning (no zero-egress local inference).
- **Proposed approach:** introduce a provider abstraction behind the executor (a thin adapter or a
  LiteLLM-style shim) so a node's model field selects provider+model; add OpenAI + Anthropic first,
  then Ollama for local. Keep the Gemini/`google.adk` path as one adapter. Surface model choice on
  the LLM/agent node and in Compare mode. Add per-provider credential handling (already have
  encrypted credentials).
- **Effort:** L (touches executor, node schema, credentials, config, Compare UI).

### P0.2 · Bidirectional MCP (client + real server)
- **Gap:** Aegis only produces an MCP tool **descriptor** (serialization in `deploy_descriptor.py`
  shown in the Deploy sheet). There is **no MCP client** (agents cannot consume external MCP
  servers/tools), and the "server" side is a JSON spec + HTTP `/v1/invoke`, not a live MCP protocol
  endpoint.
- **Why it matters:** the research is explicit — "MCP support has become a decisive differentiator
  in 2026," and n8n, Make, Dify, Langflow, Zapier, Vellum, and LangGraph are all bidirectional.
  MCP is also the cheapest way to neutralize the connector-breadth gap (P1.3): an MCP client lets
  agents reach any external tool without building connectors.
- **Proposed approach:** (a) **MCP client node/tool** — let an agent connect to an external MCP
  server (URL + auth), list its tools, and call them; (b) **real MCP server endpoint** — expose a
  published workflow over the MCP protocol (not just a descriptor) so external clients
  (Claude/Cursor/ChatGPT) can invoke it as a tool.
- **Effort:** M–L (new node + protocol endpoint; descriptor work already exists as a base).

---

## P1 — Depth gaps vs the leaders

### P1.1 · RAG depth (Knowledge Pipeline)
- **Gap:** `kb_retrieve` exists but is likely single-store/basic vs Dify's Knowledge Pipeline
  (document-ingestion UI, chunking strategies, **hybrid retrieval + reranking**, multimodal,
  connectors to Drive/Notion/S3).
- **Why it matters:** knowledge-grounded assistants are a primary use case; shallow retrieval
  reads as thin against Dify (the category RAG benchmark).
- **Proposed approach:** a knowledge-base management surface (ingest → chunk → embed → index),
  hybrid (vector + keyword) retrieval with a rerank step, and a couple of source connectors.
  **Confirm current depth before scoping.**
- **Effort:** M–L.

### P1.2 · Evaluation rigor — online evals + CI gates
- **Gap:** have datasets/experiments/eval scores; likely missing **LLM-as-judge with custom
  rubrics**, **CI regression gating** (fail a version on quality/latency drop), and **online evals**
  sampling live production traffic at a configurable rate.
- **Why it matters:** fastest-rising axis in the research; Vellum/LangSmith lead here and n8n
  shipped native evals. Natural extension of what exists.
- **Proposed approach:** add LLM-as-judge metric type with editable rubric; a "gate on regression"
  toggle for publish; an online-eval sampler that scores a fraction of prod runs and feeds the
  dashboard.
- **Effort:** M.

### P1.3 · Durable execution / run resilience
- **Gap:** runs are in-process asyncio (we just added orphaned-run reconciliation); no
  checkpointing / resume-after-failure. A restart mid-run loses the run.
- **Why it matters:** LangGraph's durable execution (checkpoint at every node, resume exactly where
  it left off) is *the* production-grade differentiator for long-running agents.
- **Proposed approach:** persist per-node state/checkpoints; on boot, resume in-flight runs instead
  of only reconciling them to failed. Consider a worker-mode execution path.
- **Effort:** L.

### P1.4 · Connector breadth (lean on MCP + HTTP, add a few first-class)
- **Gap:** ~a dozen native integrations + generic HTTP, vs 1,965 (n8n) → 9,000 (Zapier).
- **Why it matters:** breadth is a real incumbent moat — but the research's own conclusion is that
  **MCP + HTTP is the answer**, not building 500 connectors. This is why P0.2 outranks this item.
- **Proposed approach:** after MCP client lands, add a handful of high-value first-class connectors
  with OAuth credential UX (e.g., Notion, Google Drive, HTTP/GraphQL polish); otherwise defer to MCP.
- **Effort:** S per connector; ongoing.

---

## P2 — Minor / opportunistic

- **Multi-agent orchestration patterns** — first-class supervisor/agent-as-tool UX (have
  `sub_workflow` composition today, not opinionated orchestration). *S–M.*
- **Prompt playground across providers** — blocked by P0.1; unlock after multi-model. *S.*
- **Built-in data tables / stores** — for stateful workflows (cf. Zapier Tables, Make data stores).
  Have `memory_store`/`memory_retrieve`; a durable long-term store/table is the gap. *M.*
- **Plugin / community-node ecosystem** — templates exist; a marketplace (Dify/n8n style) is a
  large investment and low priority for a solo product. *L, deprioritized.*

---

## Deliberately out of scope (not gaps)

Per the MVP2 scope decisions, these are intentional omissions, **not** oversights, and should not
count against the product: collaboration/teams, RBAC, SSO/SCIM, workspaces / multi-tenant, and
monetization / pricing UI.

---

## Suggested sequencing

1. **P0.1 multi-model** and **P0.2 MCP client+server** — the two gaps a savvy evaluator notices
   immediately; do these first. They also unblock P2 prompt-playground and reduce the pressure on
   P1.4 connector breadth.
2. **P1.2 eval rigor** and **P1.1 RAG depth** — deepen the two axes where a v1 already exists.
3. **P1.3 durable execution** — when workflows get long-running or worker-mode is needed.
4. P1.4 / P2 as opportunistic follow-ons.
