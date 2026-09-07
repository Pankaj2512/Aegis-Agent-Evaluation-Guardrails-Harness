from app.services.graph_defaults import wrap_graph_with_trigger_end

WORKFLOW_TEMPLATES: list[dict] = [
    {
        "id": "research-agent",
        "name": "Research Agent",
        "description": "Search the web, synthesize findings, and evaluate response quality.",
        "graph_json": wrap_graph_with_trigger_end(
            [
                {
                    "id": "n1",
                    "position": {"x": 380, "y": 120},
                    "data": {
                        "label": "Web Search",
                        "nodeType": "tool",
                        "toolType": "search",
                        "searchProvider": "google",
                    },
                },
                {
                    "id": "n2",
                    "position": {"x": 640, "y": 120},
                    "data": {
                        "label": "Research Agent",
                        "nodeType": "agent",
                        "instruction": (
                            "Synthesize the search results into a clear, factual summary for: "
                            "{{input.query}}. Cite key findings and note any uncertainties."
                        ),
                    },
                },
                {
                    "id": "n3",
                    "position": {"x": 900, "y": 120},
                    "data": {
                        "label": "RAG Evaluation",
                        "nodeType": "evaluation",
                        "evalPreset": "rag_quality",
                        "criteria": "faithfulness, helpfulness, relevance, and toxicity",
                    },
                },
            ],
            [
                {"id": "e1", "source": "n1", "target": "n2"},
                {"id": "e2", "source": "n2", "target": "n3"},
            ],
            entry_id="n1",
            exit_id="n3",
            input_fields=[
                {"key": "query", "type": "string", "required": True},
            ],
        ),
    },
    {
        "id": "calculator-chain",
        "name": "Calculator Chain",
        "description": "Agent interprets a math problem, calculator solves it, guardrail validates output.",
        "graph_json": wrap_graph_with_trigger_end(
            [
                {
                    "id": "n1",
                    "position": {"x": 380, "y": 120},
                    "data": {
                        "label": "Math Agent",
                        "nodeType": "agent",
                        "instruction": (
                            "Convert this problem into a single math expression: {{input.problem}}. "
                            "Return only the expression, e.g. 15 * 7."
                        ),
                    },
                },
                {
                    "id": "n2",
                    "position": {"x": 640, "y": 120},
                    "data": {"label": "Calculator", "nodeType": "tool", "toolType": "calculator"},
                },
                {
                    "id": "n3",
                    "position": {"x": 900, "y": 120},
                    "data": {
                        "label": "Output Guardrail",
                        "nodeType": "guardrail",
                        "rules": {
                            "pattern": r"^-?\d+(\.\d+)?$",
                            "fail_behavior": "block",
                            "mode": "output",
                        },
                    },
                },
            ],
            [
                {"id": "e1", "source": "n1", "target": "n2"},
                {"id": "e2", "source": "n2", "target": "n3"},
            ],
            entry_id="n1",
            exit_id="n3",
            input_fields=[
                {"key": "problem", "type": "string", "required": True},
            ],
        ),
    },
    {
        "id": "support-bot",
        "name": "Support Bot",
        "description": "Validate input, generate a support response, and evaluate tone.",
        "graph_json": wrap_graph_with_trigger_end(
            [
                {
                    "id": "n1",
                    "position": {"x": 380, "y": 120},
                    "data": {
                        "label": "Input Guardrail",
                        "nodeType": "guardrail",
                        "rules": {
                            "blocked_keywords": ["spam", "hack"],
                            "detect_pii": True,
                            "fail_behavior": "block",
                            "mode": "input",
                        },
                    },
                },
                {
                    "id": "n2",
                    "position": {"x": 640, "y": 120},
                    "data": {
                        "label": "Support Agent",
                        "nodeType": "agent",
                        "instruction": (
                            "You are a professional customer support agent. "
                            "Respond empathetically to: {{input.message}}"
                        ),
                    },
                },
                {
                    "id": "n3",
                    "position": {"x": 900, "y": 120},
                    "data": {
                        "label": "Tone Evaluation",
                        "nodeType": "evaluation",
                        "evalPreset": "support_tone",
                        "criteria": "professional support tone and helpfulness",
                    },
                },
            ],
            [
                {"id": "e1", "source": "n1", "target": "n2"},
                {"id": "e2", "source": "n2", "target": "n3"},
            ],
            entry_id="n1",
            exit_id="n3",
            input_fields=[
                {"key": "message", "type": "string", "required": True},
                ],
        ),
    },
    {
        "id": "priority-router",
        "name": "Priority Router",
        "description": "Route support requests by priority using IF branching (n8n-style).",
        "graph_json": wrap_graph_with_trigger_end(
            [
                {
                    "id": "schema",
                    "position": {"x": 200, "y": 120},
                    "data": {
                        "label": "Input Schema",
                        "nodeType": "input_schema",
                        "inputFields": [
                            {"key": "message", "type": "string", "required": True},
                            {"key": "priority", "type": "string", "default": "normal"},
                        ],
                    },
                },
                {
                    "id": "if1",
                    "position": {"x": 420, "y": 120},
                    "data": {
                        "label": "High Priority?",
                        "nodeType": "if",
                        "ifCondition": {
                            "left": "{{input.priority}}",
                            "operator": "eq",
                            "right": "high",
                        },
                    },
                },
                {
                    "id": "urgent",
                    "position": {"x": 640, "y": 40},
                    "data": {
                        "label": "Urgent Agent",
                        "nodeType": "agent",
                        "instruction": (
                            "URGENT support request — respond immediately and concisely to: "
                            "{{input.message}}"
                        ),
                    },
                },
                {
                    "id": "normal",
                    "position": {"x": 640, "y": 200},
                    "data": {
                        "label": "Standard Agent",
                        "nodeType": "agent",
                        "instruction": (
                            "Respond professionally and thoroughly to: {{input.message}}"
                        ),
                    },
                },
                {
                    "id": "join",
                    "position": {"x": 900, "y": 120},
                    "data": {"label": "Join", "nodeType": "join"},
                },
            ],
            [
                {"id": "e1", "source": "schema", "target": "if1"},
                {
                    "id": "e2",
                    "source": "if1",
                    "target": "urgent",
                    "label": "true",
                    "data": {"route": "true"},
                },
                {
                    "id": "e3",
                    "source": "if1",
                    "target": "normal",
                    "label": "false",
                    "data": {"route": "false"},
                },
                {"id": "e4", "source": "urgent", "target": "join"},
                {"id": "e5", "source": "normal", "target": "join"},
            ],
            entry_id="schema",
            exit_id="join",
        ),
    },
    {
        "id": "kb-agent",
        "name": "Knowledge Agent",
        "description": "Retrieve KB context, then answer with an LLM agent (Lyzr RAG pattern).",
        "graph_json": wrap_graph_with_trigger_end(
            [
                {
                    "id": "kb",
                    "position": {"x": 380, "y": 120},
                    "data": {
                        "label": "KB Retrieve",
                        "nodeType": "kb_retrieve",
                        "kbQuery": "{{input.query}}",
                        "kbTopK": 3,
                        "kbSource": "workflow",
                        "kbMethod": "embedding",
                    },
                },
                {
                    "id": "agent",
                    "position": {"x": 640, "y": 120},
                    "data": {
                        "label": "Support Agent",
                        "nodeType": "agent",
                        "instruction": (
                            "Answer using only the retrieved context: {{steps.kb.output}}. "
                            "Question: {{input.query}}"
                        ),
                    },
                },
            ],
            [{"id": "e1", "source": "kb", "target": "agent"}],
            entry_id="kb",
            exit_id="agent",
            input_fields=[{"key": "query", "type": "string", "required": True}],
        ),
    },
    {
        "id": "memory-assistant",
        "name": "Memory Assistant",
        "description": "Store conversation context persistently and retrieve it on follow-up turns.",
        "graph_json": wrap_graph_with_trigger_end(
            [
                {
                    "id": "retrieve",
                    "position": {"x": 380, "y": 120},
                    "data": {
                        "label": "Recall Memory",
                        "nodeType": "memory_retrieve",
                        "memoryNamespace": "chat",
                        "memoryKey": "{{input.user_id}}",
                    },
                },
                {
                    "id": "agent",
                    "position": {"x": 640, "y": 120},
                    "data": {
                        "label": "Assistant",
                        "nodeType": "agent",
                        "instruction": (
                            "Prior context: {{steps.retrieve.output}}. "
                            "User ({{input.user_id}}): {{input.message}}"
                        ),
                    },
                },
                {
                    "id": "store",
                    "position": {"x": 900, "y": 120},
                    "data": {
                        "label": "Save Turn",
                        "nodeType": "memory_store",
                        "memoryNamespace": "chat",
                        "memoryKey": "{{input.user_id}}",
                        "memoryValue": "{{steps.agent.output}}",
                        "memoryPersistent": True,
                    },
                },
            ],
            [
                {"id": "e1", "source": "retrieve", "target": "agent"},
                {"id": "e2", "source": "agent", "target": "store"},
            ],
            entry_id="retrieve",
            exit_id="store",
            input_fields=[
                {"key": "user_id", "type": "string", "required": True},
                {"key": "message", "type": "string", "required": True},
            ],
        ),
    },
    {
        "id": "human-approval-gate",
        "name": "Human Approval Gate",
        "description": "Draft a response, pause for human review, then evaluate output quality.",
        "graph_json": wrap_graph_with_trigger_end(
            [
                {
                    "id": "n1",
                    "position": {"x": 380, "y": 120},
                    "data": {
                        "label": "Draft Agent",
                        "nodeType": "agent",
                        "instruction": (
                            "Draft a clear, professional response to: {{input.request}}. "
                            "Keep it concise and actionable."
                        ),
                    },
                },
                {
                    "id": "n2",
                    "position": {"x": 640, "y": 120},
                    "data": {
                        "label": "Human Review",
                        "nodeType": "human_approval",
                        "approvalReview": "Please review this draft:\n\n{{last_output}}",
                    },
                },
                {
                    "id": "n3",
                    "position": {"x": 900, "y": 120},
                    "data": {
                        "label": "Quality Check",
                        "nodeType": "evaluation",
                        "evalPreset": "support_tone",
                        "criteria": "professional tone, clarity, and helpfulness",
                    },
                },
            ],
            [
                {"id": "e1", "source": "n1", "target": "n2"},
                {"id": "e2", "source": "n2", "target": "n3"},
            ],
            entry_id="n1",
            exit_id="n3",
            input_fields=[
                {"key": "request", "type": "string", "required": True},
            ],
        ),
    },
    {
        "id": "scheduled-digest",
        "name": "Scheduled Digest",
        "description": "Cron-triggered daily summary agent (n8n Schedule Trigger pattern).",
        "graph_json": wrap_graph_with_trigger_end(
            [
                {
                    "id": "n1",
                    "position": {"x": 380, "y": 120},
                    "data": {
                        "label": "Digest Agent",
                        "nodeType": "agent",
                        "instruction": (
                            "Produce a concise daily digest of key product and team updates. "
                            "Keep it under 200 words with bullet points."
                        ),
                    },
                },
            ],
            [],
            entry_id="n1",
            exit_id="n1",
            trigger_type="schedule",
            schedule_cron="0 9 * * *",
        ),
    },
]