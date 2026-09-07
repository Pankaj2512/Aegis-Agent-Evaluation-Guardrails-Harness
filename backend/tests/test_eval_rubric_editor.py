"""Custom rubric editor: eval-preset update (PATCH) + live sample preview.

The Gemini call in preview is not exercised (no key in tests) — the no-key path
degrades to a ``skipped`` marker. Editing is verified end to end through the API.
"""

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.eval_preview import preview_eval

client = TestClient(app)


def test_update_preset_edits_rubric():
    created = client.post(
        "/api/eval-presets",
        json={
            "name": "rubric_edit_test",
            "label": "Original",
            "criteria": "original criteria",
            "score_weights": {"faithfulness": 0.25, "helpfulness": 0.25, "relevance": 0.25, "toxicity": 0.25},
        },
    ).json()
    preset_id = created["id"]

    resp = client.patch(
        f"/api/eval-presets/{preset_id}",
        json={
            "label": "Tuned rubric",
            "criteria": "faithfulness above all",
            "score_weights": {"faithfulness": 0.7, "helpfulness": 0.1, "relevance": 0.1, "toxicity": 0.1},
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["label"] == "Tuned rubric"
    assert body["criteria"] == "faithfulness above all"
    assert body["score_weights"]["faithfulness"] == 0.7

    # The edit persists in the listing.
    listed = client.get("/api/eval-presets").json()
    match = next(p for p in listed if p["id"] == preset_id)
    assert match["label"] == "Tuned rubric"

    client.delete(f"/api/eval-presets/{preset_id}")


def test_update_missing_preset_is_404():
    resp = client.patch(
        "/api/eval-presets/00000000-0000-0000-0000-0000000000ff",
        json={"label": "x"},
    )
    assert resp.status_code == 404


def test_preview_without_key_skips(monkeypatch):
    monkeypatch.setattr(settings, "google_api_key", "", raising=False)
    result = preview_eval("some question", "some answer", criteria="clarity")
    assert result["skipped"] is True
    assert result["aggregate_score"] is None


def test_preview_endpoint_no_key(monkeypatch):
    monkeypatch.setattr(settings, "google_api_key", "", raising=False)
    resp = client.post(
        "/api/eval-presets/preview",
        json={"input_text": "q", "output_text": "a", "criteria": "clarity"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["skipped"] is True
