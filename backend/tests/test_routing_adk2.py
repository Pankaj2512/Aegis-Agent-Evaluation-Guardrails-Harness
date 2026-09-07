"""Regression: conditional routing must work under ADK 2.x.

ADK 2.x routes exclusively via ctx.route — decision objects returned from
function nodes are treated as plain output. These tests run a real compiled
workflow through the ADK Runner (no LLM calls: trigger/if/transform only)
and assert the correct branch executes. Guards against the silent breakage
where every routed edge went dark and workflows "completed" after the IF node.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.services.compiler import compile_workflow


def _branch_graph(operator: str = "contains", right: str = "yes") -> dict:
    return {
        "nodes": [
            {"id": "n1", "data": {"label": "Trigger", "nodeType": "trigger", "triggerType": "manual"}},
            {
                "id": "n2",
                "data": {
                    "label": "IF",
                    "nodeType": "if",
                    "ifCondition": {"left": "{{input.text}}", "operator": operator, "right": right},
                },
            },
            {"id": "n3", "data": {"label": "Yes", "nodeType": "transform", "template": "YES:{{last_output}}"}},
            {"id": "n4", "data": {"label": "No", "nodeType": "transform", "template": "NO:{{last_output}}"}},
            {"id": "n5", "data": {"label": "End", "nodeType": "end"}},
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n2", "target": "n3", "data": {"route": "true"}},
            {"id": "e3", "source": "n2", "target": "n4", "data": {"route": "false"}},
            {"id": "e4", "source": "n3", "target": "n5"},
            {"id": "e5", "source": "n4", "target": "n5"},
        ],
    }


async def _run_graph(graph: dict, input_text: str) -> dict:
    context_ref: dict = {"input": {"text": input_text}, "steps": {}, "last_output": input_text}
    workflow, _metadata, _lookup = compile_workflow(graph, context_ref=context_ref)
    runner = Runner(
        app_name="test",
        node=workflow,
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )
    async for _event in runner.run_async(
        user_id="test-user",
        session_id=str(uuid.uuid4()),
        new_message=types.Content(parts=[types.Part(text=input_text)]),
    ):
        pass
    return context_ref


@pytest.mark.parametrize(
    ("input_text", "expected_branch", "unexpected_branch", "expected_route"),
    [
        ("yes please", "n3", "n4", "true"),
        ("absolutely not", "n4", "n3", "false"),
    ],
)
def test_if_routes_correct_branch(input_text, expected_branch, unexpected_branch, expected_route):
    ctx = asyncio.run(_run_graph(_branch_graph(), input_text))
    steps = ctx.get("steps", {})
    assert expected_branch in steps, f"branch {expected_branch} did not execute; steps={list(steps)}"
    assert unexpected_branch not in steps, f"wrong branch executed; steps={list(steps)}"
    assert ctx.get("routes", {}).get("n2", {}).get("route") == expected_route
    # decision nodes pass content through — downstream saw the original text
    assert input_text in steps[expected_branch]["output"]
    # the workflow reached the end
    assert "n5" in steps


def test_if_decision_is_not_leaked_as_output():
    ctx = asyncio.run(_run_graph(_branch_graph(), "yes indeed"))
    if_output = ctx["steps"]["n2"]["output"]
    assert "route=" not in if_output, "RouterDecision leaked into node output"
