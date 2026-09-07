# Aegis — System Architecture

Aegis is a visual agent-workflow workbench: users compose graph workflows (LLM agents, tools,
routers, guardrails, evals) on a React Flow canvas, run them against real inputs via Google ADK +
Gemini, and operate them through an observability/triage surface. Two apps live in one repo:
`backend/` (FastAPI, Python 3.12) and `frontend/` (Next.js 14 App Router, TypeScript).

The diagrams below are Mermaid and render directly on GitHub.

## 1. System overview

The frontend never talks to Gemini and never touches the database — every call goes through the
typed client (`frontend/src/lib/api.ts`) to the FastAPI backend. Server-sent events (run stream,
observability stream) are proxied through Next.js route handlers under `src/app/api/*/stream/`
rather than hitting the backend directly.

```mermaid
flowchart LR
    subgraph browser["Browser"]
        UI["Next.js 14 App Router UI<br/>React Flow canvas · TanStack Query<br/>frontend/src"]
    end
    subgraph nextsrv["Next.js server"]
        PROXY["SSE proxy route handlers<br/>src/app/api/*/stream"]
    end
    subgraph fastapi["FastAPI backend (port 8000)"]
        MW["Middleware: CORS · optional X-Aegis-API-Key auth<br/>viewer role · rate limits"]
        ROUTERS["Routers — app/api/*"]
        SVC["Services — app/services/* (~60 modules)"]
        EXEC["Executor + in-memory run event broker"]
    end
    DB[("Postgres (prod) / SQLite (dev, tests)<br/>schema owned by Alembic")]
    ADK["Google ADK Runner"]
    GEMINI["Gemini models"]

    UI -->|"typed client — src/lib/api.ts"| MW
    UI -->|"EventSource"| PROXY -->|"SSE"| MW
    MW --> ROUTERS --> SVC --> DB
    SVC --> EXEC --> ADK --> GEMINI
```

## 2. Run pipeline (the core loop)

Workflow graphs are stored as JSON (`nodes` + `edges`). A run passes through three services in
order: **validation** (`graph_validation.py`, must be Trigger → … → End, acyclic, no orphan
edges), **compilation** (`compiler.py`, graph JSON → ADK `Workflow`; non-LLM node behaviors come
from `_make_*_fn` factories in `node_handlers.py`), and **execution** (`executor.py`, streams node
events to SSE subscribers through the in-memory `_RunEventBroker`, applies guardrail policies and
eval thresholds, and records observability rollups).

```mermaid
sequenceDiagram
    autonumber
    participant UI as Frontend
    participant API as app/api/runs.py
    participant VAL as graph_validation.py
    participant CMP as compiler.py
    participant EXE as executor.py
    participant ADK as ADK Runner + Gemini
    participant DB as Database

    UI->>API: POST run (workflow, input)
    API->>VAL: validate DAG (Trigger → … → End, acyclic)
    API->>DB: create WorkflowRun
    API->>EXE: schedule (inline) / worker claims (worker mode)
    EXE->>CMP: compile_workflow(graph JSON)
    CMP-->>EXE: ADK Workflow (agents, join nodes, routed edges)
    EXE->>ADK: execute via Runner
    ADK-->>EXE: node events (streamed)
    EXE-->>UI: SSE via _RunEventBroker (through Next proxy)
    EXE->>EXE: apply guardrail policies + eval thresholds
    EXE->>DB: NodeResult · LlmCall · RunSpan · observability rollups
```

## 3. Backend layering

Strict layering: routers parse and authorize, schemas shape the payloads, services hold all
business logic, and a single SQLAlchemy models file talks to the database. All settings live in
`app/config.py` (`Settings`) — env vars are never read directly. The app deliberately does **not**
call `Base.metadata.create_all()` on startup; `app/services/startup.py` gates boot on the database
being at Alembic head.

```mermaid
flowchart TB
    MW["app/main.py — FastAPI app<br/>CORS · optional API-key auth + viewer role · rate limits · lifespan"]
    R["app/api — 16 routers, one per resource<br/>workflows · runs · observability · credentials · guardrail_policies<br/>datasets · experiments · feedback · alerts · templates · jobs<br/>eval_presets · node_test · assist · meta · platform"]
    S["app/schemas — Pydantic request/response models"]
    SVC["app/services — all business logic (~60 modules)<br/>graph_validation · compiler · node_handlers · executor<br/>guardrail* · eval* · observability_* · knowledge_* · credentials (Fernet)<br/>run_worker · schedule_worker · job_queue · tracing"]
    M["app/db/models.py — single SQLAlchemy models file"]
    DB[("Postgres / SQLite")]
    AL["alembic/ — owns the schema<br/>startup gate: DB must be at head"]
    CFG["app/config.py — Settings<br/>(only place env is read)"]

    MW --> R --> S --> SVC --> M --> DB
    AL -.->|"migrations"| DB
    CFG -.-> MW
    CFG -.-> SVC
```

## 4. Node type system (spans both apps)

Adding or changing a node type touches a fixed set of files that must stay in sync across the two
apps. The backend registry (`node_registry.py`) is canonical and is served to the UI.

```mermaid
flowchart LR
    NT(["A node type<br/>(e.g. agent, guardrail, router)"])
    subgraph BE["Backend — backend/app/services"]
        REG["node_registry.py<br/>canonical metadata, served to the UI"]
        NH["node_handlers.py<br/>_make_*_fn execution factory"]
        CP["compiler.py<br/>wiring into the ADK Workflow"]
        GV["graph_validation.py<br/>structural rules (if any)"]
    end
    subgraph FE["Frontend — frontend/src"]
        TW["types/workflow.ts<br/>NodeType union + node data types"]
        NR["lib/node-registry.ts<br/>labels · icons · categories"]
        CN["components/canvas/nodes/*<br/>canvas renderer component"]
    end
    NT --> REG
    NT --> NH
    NT --> CP
    NT --> GV
    NT --> TW
    NT --> NR
    NT --> CN
```

The registry currently defines 30 node types across six categories:

| Category | Node types |
|---|---|
| `flow` (12) | trigger, end, input_schema, if, switch, filter, human_approval, sub_workflow, router, classifier, join, iteration |
| `data` (8) | transform, set_fields, code, memory_store, memory_retrieve, kb_retrieve, json_parse, delay |
| `llm` (4) | agent, summarizer, translator, extractor |
| `tools` (2) | tool, integration |
| `quality` (2) | evaluation, guardrail |
| `annotate` (2) | note, group (neither is executable) |

`frontend/src/types/workflow.ts` mirrors all 30 in its `NodeType` union. The palette in
`frontend/src/lib/node-registry.ts` intentionally defines only 29 — `group` is a display-only frame
created from the canvas toolbar, not dragged in from the palette.

## 5. Execution modes and the single-process constraint

`RUN_EXECUTION_MODE=inline` (default) executes runs inside the API process. In `worker` mode a
separate `worker.py` process claims and executes runs — the API must not also start the run worker
(split-brain double-claim). SSE streams and human-approval waits live in in-memory state in the
executor, so in worker mode `/stream` and `/approve` served by the API cannot see them. This is a
known constraint; don't "fix" it casually. The schedule worker (cron-style triggers) runs in the
API lifespan in both modes.

```mermaid
flowchart TB
    subgraph inline["RUN_EXECUTION_MODE=inline (default)"]
        API1["API process<br/>create_run schedules directly"] --> EX1["executor (same process)"]
        EX1 --> BR1["in-memory _RunEventBroker<br/>SSE /stream + /approve waits work"]
    end
    subgraph workermode["RUN_EXECUTION_MODE=worker"]
        API2["API process<br/>must NOT start the run worker"] -->|"writes pending run"| DB2[("Database")]
        W["worker.py process"] -->|"claims + executes"| DB2
        W --> EX2["executor (worker process)<br/>broker + approval state live here"]
        API2 -. "/stream and /approve cannot see<br/>worker memory — known constraint" .- EX2
    end
```

## 6. Data model (key relationships)

A single SQLAlchemy models file (`app/db/models.py`, 22 tables). The core chain is
workflow → version → run → per-node observability records. Standalone tables not shown:
`observability_rollups`, `background_jobs`, `evaluation_presets`, `credentials` (Fernet-encrypted
secrets when `APP_ENCRYPTION_KEY` is set), `guardrail_policies`, `workflow_templates`, `audit_log`.

```mermaid
erDiagram
    workflows ||--o{ workflow_versions : "has versions"
    workflow_versions ||--o{ workflow_runs : "is executed as"
    workflows ||--o{ workflow_memory : "persists memory"
    workflows ||--o{ knowledge_documents : "indexes KB docs"
    workflows ||--o| workflow_schedules : "has schedule"
    workflow_schedules }o--|| workflow_versions : "pins version"
    workflow_runs ||--o{ node_results : "produces"
    workflow_runs ||--o{ llm_calls : "records"
    workflow_runs ||--o{ run_spans : "traces"
    run_spans ||--o{ run_spans : "parent span"
    workflow_runs ||--o{ feedback : "receives"
    workflows ||--o{ datasets : "owns"
    datasets ||--o{ dataset_items : "contains"
    workflows ||--o{ experiments : "runs"
    datasets ||--o{ experiments : "feeds"
    alert_rules ||--o{ alert_events : "fires"
```
