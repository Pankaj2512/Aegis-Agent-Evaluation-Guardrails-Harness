# Aegis MVP1 Design Spec

## Goal
Visual agent workflow platform with evaluation and guardrails as first-class features.

## Tech Stack
- Frontend: Next.js 14, TypeScript, Tailwind, shadcn/ui, React Flow
- Backend: FastAPI, SQLAlchemy, PostgreSQL
- LLM: Google Gemini API (`gemini-2.5-flash`)
- Execution: Google ADK 2.0 graph `Workflow`

## Search Tools
- Default: Google Search (ADK `google_search` tool)
- Options: EXA (`EXA_API_KEY`), DuckDuckGo (no key)

## Node Types
| Canvas | ADK |
|--------|-----|
| LLM Agent | `Agent` |
| Tool (Calculator) | `FunctionNode` |
| Tool (Search) | `Agent` (Google) or `FunctionNode` (EXA/DDG) |
| Evaluation | `Agent` with structured judge output |
| Guardrail | `FunctionNode` validation |

## API
- `GET/POST /api/workflows`
- `GET /api/workflows/{id}`
- `POST /api/workflows/{id}/versions`
- `POST /api/runs` — start execution
- `GET /api/runs` — list runs
- `GET /api/runs/{id}` — run details
- `GET /api/runs/{id}/stream` — SSE progress

## Out of Scope
Auth, branching/loops on canvas, memory, A/B testing, deployment, collaboration.