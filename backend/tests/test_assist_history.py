"""Tests for threaded copilot history on the edit-graph / suggest-nodes assist
endpoints.

History is optional and capped server-side. These tests assert that prior turns
land in the model prompt, that the cap holds, that empty/absent history is
byte-for-byte back-compatible, and that history participates in the suggest
cache key (so a turn-3 request never serves a turn-1 cached result).
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.assist import (
    AssistHistoryTurn,
    GenEdge,
    GenNode,
    SuggestionsDraft,
    _EditGraphDraft,
)
from app.services import assist as assist_service

client = TestClient(app)


def _mock_response(model_obj) -> MagicMock:
    resp = MagicMock()
    resp.text = model_obj.model_dump_json()
    return resp


def _current_graph() -> dict:
    return {
        "nodes": [
            {"id": "trigger", "data": {"label": "T", "nodeType": "trigger", "triggerType": "manual"}},
            {"id": "agent", "data": {"label": "A", "nodeType": "agent", "instruction": "help"}},
            {"id": "end", "data": {"label": "E", "nodeType": "end"}},
        ],
        "edges": [
            {"id": "e1", "source": "trigger", "target": "agent"},
            {"id": "e2", "source": "agent", "target": "end"},
        ],
    }


def _valid_edit_draft() -> _EditGraphDraft:
    return _EditGraphDraft(
        nodes=[
            GenNode(id="trigger", node_type="trigger", label="T", config_json='{"triggerType": "manual"}'),
            GenNode(id="agent", node_type="agent", label="A", config_json='{"instruction": "help"}'),
            GenNode(id="end", node_type="end", label="E", config_json=None),
        ],
        edges=[
            GenEdge(source="trigger", target="agent", route=None),
            GenEdge(source="agent", target="end", route=None),
        ],
        notes=[],
        summary="No structural change.",
    )


def _suggest_graph() -> dict:
    return {
        "nodes": [
            {"id": "trigger", "data": {"label": "T", "nodeType": "trigger"}},
            {"id": "agent", "data": {"label": "A", "nodeType": "agent"}},
            {"id": "end", "data": {"label": "E", "nodeType": "end"}},
        ],
        "edges": [
            {"id": "e1", "source": "trigger", "target": "agent"},
            {"id": "e2", "source": "agent", "target": "end"},
        ],
    }


def _last_prompt(mock_client: MagicMock) -> str:
    return mock_client.models.generate_content.call_args.kwargs["contents"]


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------


def test_capped_history_takes_last_8_and_drops_blanks():
    turns = [AssistHistoryTurn(role="user", content=f"turn-{i}") for i in range(10)]
    turns.insert(0, AssistHistoryTurn(role="assistant", content="   "))  # blank -> dropped
    kept = assist_service._capped_history(turns)
    assert len(kept) == 8
    assert kept[0].content == "turn-2"
    assert kept[-1].content == "turn-9"


def test_format_history_empty_is_blank():
    assert assist_service._format_history(None) == ""
    assert assist_service._format_history([]) == ""


def test_history_cache_fragment_distinguishes_content():
    h1 = [AssistHistoryTurn(role="user", content="add a guardrail")]
    h2 = [AssistHistoryTurn(role="user", content="remove the guardrail")]
    assert assist_service._history_cache_fragment(None) == ""
    assert assist_service._history_cache_fragment(h1) != ""
    assert assist_service._history_cache_fragment(h1) != assist_service._history_cache_fragment(h2)


# ---------------------------------------------------------------------------
# edit-graph history
# ---------------------------------------------------------------------------


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_edit_graph_history_included_in_prompt(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_response(_valid_edit_draft())

    resp = client.post(
        "/api/assist/edit-graph",
        json={
            "graph": _current_graph(),
            "instruction": "undo that last change",
            "history": [
                {"role": "user", "content": "add a guardrail after the agent"},
                {"role": "assistant", "content": "Added an output guardrail — user applied it"},
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    prompt = _last_prompt(mock_client)
    assert "PRIOR CONVERSATION" in prompt
    assert "add a guardrail after the agent" in prompt
    assert "Added an output guardrail — user applied it" in prompt
    # History sits between the current workflow and the new instruction.
    assert prompt.index("PRIOR CONVERSATION") < prompt.index("USER INSTRUCTION")


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_edit_graph_history_capped_at_8(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_response(_valid_edit_draft())

    history = [{"role": "user", "content": f"turn-{i}"} for i in range(10)]
    resp = client.post(
        "/api/assist/edit-graph",
        json={"graph": _current_graph(), "instruction": "next", "history": history},
    )
    assert resp.status_code == 200, resp.text
    prompt = _last_prompt(mock_client)
    # Only the last 8 turns survive.
    assert "turn-0" not in prompt
    assert "turn-1" not in prompt
    assert "turn-2" in prompt
    assert "turn-9" in prompt


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_edit_graph_without_history_is_backcompat(mock_client_cls):
    """Absent/empty history -> no history block, endpoint behaves as before."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_response(_valid_edit_draft())

    # No history key at all.
    resp = client.post(
        "/api/assist/edit-graph",
        json={"graph": _current_graph(), "instruction": "do nothing"},
    )
    assert resp.status_code == 200, resp.text
    prompt_absent = _last_prompt(mock_client)
    assert "PRIOR CONVERSATION" not in prompt_absent
    assert "proposed_graph" in resp.json()

    # Explicit empty history -> identical prompt.
    resp2 = client.post(
        "/api/assist/edit-graph",
        json={"graph": _current_graph(), "instruction": "do nothing", "history": []},
    )
    assert resp2.status_code == 200, resp2.text
    assert _last_prompt(mock_client) == prompt_absent


# ---------------------------------------------------------------------------
# suggest-nodes history
# ---------------------------------------------------------------------------


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_suggest_nodes_history_included_in_prompt(mock_client_cls):
    assist_service._SUGGEST_CACHE.clear()
    draft = SuggestionsDraft(
        suggestions=[{"node_type": "guardrail", "label": "Safety", "reason": "protect"}]
    )
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_response(draft)

    resp = client.post(
        "/api/assist/suggest-nodes",
        json={
            "graph": _suggest_graph(),
            "selected_node_id": "agent",
            "history": [{"role": "user", "content": "make it safer for compliance"}],
        },
    )
    assert resp.status_code == 200, resp.text
    prompt = _last_prompt(mock_client)
    assert "PRIOR CONVERSATION" in prompt
    assert "make it safer for compliance" in prompt


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_suggest_nodes_history_is_part_of_cache_key(mock_client_cls):
    """Different history -> cache miss; same history -> cache hit."""
    assist_service._SUGGEST_CACHE.clear()
    draft = SuggestionsDraft(
        suggestions=[{"node_type": "guardrail", "label": "Safety", "reason": "protect"}]
    )
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_response(draft)

    graph = _suggest_graph()
    h1 = {"graph": graph, "selected_node_id": "agent", "history": [{"role": "user", "content": "turn one"}]}
    h2 = {"graph": graph, "selected_node_id": "agent", "history": [{"role": "user", "content": "turn two"}]}

    client.post("/api/assist/suggest-nodes", json=h1)  # miss -> 1 call
    client.post("/api/assist/suggest-nodes", json=h2)  # different history -> miss -> 2 calls
    client.post("/api/assist/suggest-nodes", json=h1)  # same as first -> hit -> still 2
    assert mock_client.models.generate_content.call_count == 2


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_suggest_nodes_no_history_matches_prior_cache_shape(mock_client_cls):
    """History-free calls still cache against each other (byte-compat key)."""
    assist_service._SUGGEST_CACHE.clear()
    draft = SuggestionsDraft(
        suggestions=[{"node_type": "guardrail", "label": "Safety", "reason": "protect"}]
    )
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_response(draft)

    payload = {"graph": _suggest_graph(), "selected_node_id": "agent"}
    client.post("/api/assist/suggest-nodes", json=payload)
    client.post("/api/assist/suggest-nodes", json=payload)
    assert mock_client.models.generate_content.call_count == 1
