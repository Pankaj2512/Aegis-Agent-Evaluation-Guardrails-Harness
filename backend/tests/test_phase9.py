import json

from fastapi.testclient import TestClient

from app.main import app
from app.services.workflow_import import WorkflowImportError, normalize_workflow_import
from tests.conftest import valid_graph

client = TestClient(app)


def _sample_export(name: str = "Export Test") -> dict:
    graph = valid_graph(
        [
            {
                "id": "n1",
                "position": {"x": 100, "y": 0},
                "data": {"label": "Transform", "nodeType": "transform", "transformTemplate": "hi"},
            }
        ],
    )
    return {
        "format": "aegis-workflow-v1",
        "workflow_id": "00000000-0000-0000-0000-000000000001",
        "name": name,
        "description": "Exported for tests",
        "version_number": 1,
        "graph_json": graph,
        "exported_at": "2026-06-30T12:00:00",
    }


def test_normalize_workflow_import_accepts_export():
    export = _sample_export()
    name, description, graph = normalize_workflow_import(export)
    assert name == "Export Test"
    assert description == "Exported for tests"
    assert "nodes" in graph
    assert any(n["data"]["nodeType"] == "trigger" for n in graph["nodes"])


def test_normalize_workflow_import_rejects_bad_format():
    export = _sample_export()
    export["format"] = "n8n-v1"
    try:
        normalize_workflow_import(export)
        assert False, "expected WorkflowImportError"
    except WorkflowImportError as exc:
        assert "Unsupported format" in str(exc)


def test_import_workflow_creates_new_workflow():
    export = _sample_export("Imported Flow")
    response = client.post("/api/workflows/import", json=export)
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Imported Flow"
    assert body["description"] == "Exported for tests"
    assert body["latest_version"]["graph_json"]["nodes"]
    assert body["id"] != export["workflow_id"]


def test_import_into_existing_workflow_versions_graph():
    created = client.post(
        "/api/workflows",
        json={
            "name": "Target",
            "graph_json": valid_graph(
                [
                    {
                        "id": "n1",
                        "position": {"x": 0, "y": 0},
                        "data": {"label": "Delay", "nodeType": "delay", "delayMs": 1},
                    }
                ],
            ),
        },
    ).json()
    workflow_id = created["id"]

    export = _sample_export("Replacement Graph")
    import_response = client.post(
        f"/api/workflows/{workflow_id}/import",
        json={**export, "save_as_new_version": True},
    )
    assert import_response.status_code == 200
    version = import_response.json()
    assert version["version_number"] == 2
    assert any(
        n["data"]["nodeType"] == "transform"
        for n in version["graph_json"]["nodes"]
    )


def test_export_workflow_matches_import_format():
    created = client.post(
        "/api/workflows",
        json={
            "name": "Round Trip",
            "description": "desc",
            "graph_json": valid_graph(
                [
                    {
                        "id": "n1",
                        "position": {"x": 0, "y": 0},
                        "data": {"label": "Calc", "nodeType": "tool", "toolType": "calculator"},
                    }
                ],
            ),
        },
    ).json()
    workflow_id = created["id"]

    export_response = client.get(f"/api/workflows/{workflow_id}/export")
    assert export_response.status_code == 200
    export = export_response.json()
    assert export["format"] == "aegis-workflow-v1"
    assert export["name"] == "Round Trip"
    assert export["graph_json"]["nodes"]

    disposition = export_response.headers.get("content-disposition", "")
    assert "attachment" in disposition

    import_response = client.post("/api/workflows/import", json=export)
    assert import_response.status_code == 200
    imported = import_response.json()
    assert imported["name"] == "Round Trip"
    assert len(imported["latest_version"]["graph_json"]["nodes"]) == len(export["graph_json"]["nodes"])