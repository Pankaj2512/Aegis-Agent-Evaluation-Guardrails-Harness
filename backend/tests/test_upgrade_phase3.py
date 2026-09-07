from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth.deps import DEFAULT_DEV_USER_ID
from app.db import models
from app.db.database import SessionLocal
from app.main import app
from app.services.compiler import compile_workflow
from app.services.eval_deterministic import (
    evaluate_embedding_similarity,
    evaluate_exact,
    evaluate_regex,
    evaluate_substring,
)
from app.services.eval_preset_service import enrich_graph_eval_presets, list_all_presets
from tests.conftest import valid_graph

client = TestClient(app)


def test_evaluate_exact_match_pass_and_fail():
    passed = evaluate_exact("hello world", "hello world")
    assert passed["passed"] is True
    assert passed["aggregate_score"] == 5.0

    failed = evaluate_exact("hello", "world")
    assert failed["passed"] is False
    assert failed["aggregate_score"] == 1.0


def test_evaluate_substring_match():
    result = evaluate_substring("The refund policy allows returns within 30 days.", "refund policy")
    assert result["passed"] is True


def test_evaluate_regex_match():
    result = evaluate_regex('{"status": "ok"}', r'"status"\s*:\s*"ok"')
    assert result["passed"] is True


def test_evaluate_embedding_similarity_uses_cosine():
    result = evaluate_embedding_similarity(
        "refund policy for customers",
        "customer refund policy",
        threshold=0.5,
    )
    assert "similarity" in result
    assert result["aggregate_score"] >= 1.0


def test_compile_deterministic_eval_is_deferred():
    graph = valid_graph(
        [
            {
                "id": "eval1",
                "position": {"x": 0, "y": 0},
                "data": {
                    "label": "Regex Eval",
                    "nodeType": "evaluation",
                    "evalType": "regex",
                    "evalPattern": r"^\d+$",
                },
            },
        ],
    )
    _workflow, metadata, _ = compile_workflow(graph)
    assert metadata["eval1"]["eval_type"] == "regex"
    assert metadata["eval1"]["eval_deferred"] is True


def test_create_and_list_custom_eval_preset():
    created = client.post(
        "/api/eval-presets",
        json={
            "name": "custom_support",
            "label": "Custom Support",
            "criteria": "empathy and resolution quality",
            "score_weights": {
                "faithfulness": 0.25,
                "helpfulness": 0.35,
                "relevance": 0.25,
                "toxicity": 0.15,
            },
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["label"] == "Custom Support"

    listed = client.get("/api/eval-presets")
    assert listed.status_code == 200
    presets = listed.json()
    assert any(p["id"] == str(body["id"]) and p["source"] == "custom" for p in presets)

    deleted = client.delete(f"/api/eval-presets/{body['id']}")
    assert deleted.status_code == 200


def test_enrich_graph_injects_custom_preset_criteria():
    db = SessionLocal()
    try:
        row = models.EvaluationPreset(
            id=uuid4(),
            user_id=DEFAULT_DEV_USER_ID,
            name="enriched_preset",
            label="Enriched",
            criteria="custom criteria from db",
            score_weights={"faithfulness": 0.4, "helpfulness": 0.3, "relevance": 0.2, "toxicity": 0.1},
        )
        db.add(row)
        db.commit()

        graph = valid_graph(
            [
                {
                    "id": "eval1",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "label": "Eval",
                        "nodeType": "evaluation",
                        "evalCustomPresetId": str(row.id),
                    },
                },
            ],
        )
        enriched = enrich_graph_eval_presets(graph, db, DEFAULT_DEV_USER_ID)
        eval_node = next(node for node in enriched["nodes"] if node["id"] == "eval1")
        node_data = eval_node["data"]
        assert node_data["criteria"] == "custom criteria from db"
        assert node_data["scoreWeights"]["faithfulness"] == 0.4
    finally:
        db.close()


def test_list_all_presets_includes_builtin_and_custom():
    db = SessionLocal()
    try:
        presets = list_all_presets(db, DEFAULT_DEV_USER_ID)
        assert any(p["source"] == "builtin" for p in presets)
    finally:
        db.close()