"""Built-in guardrail policy templates (Phase 3 follow-up).

Templates are static reference data. What matters: the endpoint serves them,
each carries a well-formed guardrail rule bundle, and adopting one creates an
owned, editable policy through the normal create path.
"""

from fastapi.testclient import TestClient

from app.main import app
from app.services.guardrail import validate_guardrail_content
from app.services.guardrail_policy_templates import POLICY_TEMPLATES

client = TestClient(app)

_VALID_TYPES = {"rules", "llm", "presidio", "prompt_injection", "moderation"}


def test_templates_endpoint_lists_builtins():
    resp = client.get("/api/guardrail-policies/templates")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == len(POLICY_TEMPLATES)
    ids = {t["id"] for t in body}
    # The plan's named starting points are all present.
    assert {"pii-strict", "injection-shield", "content-moderation"} <= ids
    for t in body:
        assert t["id"] and t["name"] and t["description"] and t["category"]
        assert t["rules_json"]["guardrail_type"] in _VALID_TYPES


def test_each_template_rule_bundle_is_evaluable():
    # A template's rules must run through the guardrail path without exploding
    # (no key configured → LLM-backed rails degrade gracefully, never raise).
    for template in POLICY_TEMPLATES:
        result = validate_guardrail_content("hello world", template["rules_json"])
        assert isinstance(result.passed, bool)


def test_adopting_a_template_creates_owned_policy():
    templates = client.get("/api/guardrail-policies/templates").json()
    template = next(t for t in templates if t["id"] == "pii-strict")

    resp = client.post(
        "/api/guardrail-policies",
        json={
            "name": template["name"],
            "description": template["description"],
            "rules_json": template["rules_json"],
        },
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["rules_json"]["guardrail_type"] == "presidio"

    # The adopted copy is now an editable, owned policy.
    listed = client.get("/api/guardrail-policies").json()
    assert any(p["id"] == created["id"] for p in listed)

    client.delete(f"/api/guardrail-policies/{created['id']}")
