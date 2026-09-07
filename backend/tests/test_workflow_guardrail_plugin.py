"""Workflow-level guardrail policy plugin (ADK callbacks).

A single policy applied to every agent's model call. The plugin is exercised
directly with real genai request/response objects so the callback contract —
short-circuit on input, replace on output, warn passes through, mode gating —
is verified without standing up a full ADK run. Uses a deterministic rules-type
keyword policy so no LLM is called.
"""

import asyncio
import json
from types import SimpleNamespace

from google.adk.models.llm_response import LlmResponse
from google.genai import types

from app.services.guardrail_policy_plugin import GuardrailPolicyPlugin

BLOCK_RULES = {
    "guardrail_type": "rules",
    "blocked_keywords": ["forbidden"],
    "fail_behavior": "block",
}
WARN_RULES = {
    "guardrail_type": "rules",
    "blocked_keywords": ["forbidden"],
    "fail_behavior": "warn",
}


def _request(text: str):
    # Mirror LlmRequest: a `.contents` list of Content objects.
    return SimpleNamespace(contents=[types.Content(role="user", parts=[types.Part(text=text)])])


def _response(text: str) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


def _text_of(resp: LlmResponse) -> str:
    return resp.content.parts[0].text


# ---- pure decision logic --------------------------------------------------


def test_decide_blocks_forbidden_output():
    plugin = GuardrailPolicyPlugin(BLOCK_RULES, mode="both")
    status, override, _msg = plugin._decide("this is forbidden text", "output")
    assert status == "failed"
    assert override is None


def test_decide_passes_clean_text():
    plugin = GuardrailPolicyPlugin(BLOCK_RULES, mode="both")
    status, _override, _msg = plugin._decide("perfectly clean text", "output")
    assert status == "passed"


def test_decide_warn_behavior_does_not_fail():
    plugin = GuardrailPolicyPlugin(WARN_RULES, mode="both")
    status, override, _msg = plugin._decide("this is forbidden text", "output")
    assert status == "warned"
    assert override is None


# ---- ADK callbacks --------------------------------------------------------


def test_after_model_replaces_blocked_output():
    plugin = GuardrailPolicyPlugin(BLOCK_RULES, mode="output")
    out = asyncio.run(
        plugin.after_model_callback(callback_context=None, llm_response=_response("forbidden secret"))
    )
    assert isinstance(out, LlmResponse)
    assert "Blocked by workflow guardrail policy" in _text_of(out)
    assert plugin.blocked is True
    assert plugin.events and plugin.events[0]["status"] == "failed"
    assert plugin.events[0]["mode"] == "output"
    assert plugin.events[0]["scope"] == "workflow"


def test_after_model_passes_clean_output():
    plugin = GuardrailPolicyPlugin(BLOCK_RULES, mode="output")
    out = asyncio.run(
        plugin.after_model_callback(callback_context=None, llm_response=_response("all good here"))
    )
    assert out is None
    assert plugin.events == []


def test_before_model_short_circuits_blocked_input():
    plugin = GuardrailPolicyPlugin(BLOCK_RULES, mode="input")
    out = asyncio.run(
        plugin.before_model_callback(callback_context=None, llm_request=_request("forbidden ask"))
    )
    assert isinstance(out, LlmResponse)
    assert "Blocked by workflow guardrail policy" in _text_of(out)
    assert plugin.events[0]["mode"] == "input"


def test_mode_gating_output_only_ignores_input():
    plugin = GuardrailPolicyPlugin(BLOCK_RULES, mode="output")
    out = asyncio.run(
        plugin.before_model_callback(callback_context=None, llm_request=_request("forbidden ask"))
    )
    # Output-only policy must not touch the model input.
    assert out is None
    assert plugin.events == []


def test_warn_output_keeps_original_but_records_event():
    plugin = GuardrailPolicyPlugin(WARN_RULES, mode="output")
    out = asyncio.run(
        plugin.after_model_callback(callback_context=None, llm_response=_response("forbidden but warn"))
    )
    assert out is None  # original response kept
    assert plugin.events and plugin.events[0]["status"] == "warned"
    assert plugin.blocked is False


def test_structured_output_replacement_stays_json_parseable():
    # Aegis agents compile with output_schema=str, so the model returns a JSON
    # string and ADK json-loads the (possibly replaced) output. The block
    # replacement must itself be valid JSON or the run fails downstream.
    plugin = GuardrailPolicyPlugin(BLOCK_RULES, mode="output")
    json_encoded = _response(json.dumps("this is forbidden"))
    out = asyncio.run(
        plugin.after_model_callback(callback_context=None, llm_response=json_encoded)
    )
    assert isinstance(out, LlmResponse)
    replaced = _text_of(out)
    # Round-trips through json.loads exactly as ADK's validate_schema(str, ...) will.
    decoded = json.loads(replaced)
    assert isinstance(decoded, str)
    assert "Blocked by workflow guardrail policy" in decoded


def test_input_short_circuit_encodes_json_when_expected():
    plugin = GuardrailPolicyPlugin(BLOCK_RULES, mode="input")
    req = SimpleNamespace(
        contents=[types.Content(role="user", parts=[types.Part(text="forbidden ask")])],
        config=SimpleNamespace(response_mime_type="application/json", response_schema=str),
    )
    out = asyncio.run(plugin.before_model_callback(callback_context=None, llm_request=req))
    assert isinstance(out, LlmResponse)
    decoded = json.loads(_text_of(out))  # must be JSON since the agent expects JSON
    assert "Blocked by workflow guardrail policy" in decoded
