from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.services import tracing


def _reset_tracing() -> None:
    tracing.shutdown_tracing()
    tracing._enabled = False
    tracing._tracer = None
    tracing._provider = None


def test_tracing_disabled_by_default():
    _reset_tracing()
    tracing.init_tracing()
    assert tracing.is_tracing_enabled() is False
    assert tracing.get_trace_id() is None

    tracker = tracing.NodeSpanTracker()
    tracker.start("n1", "agent", "Agent")
    tracker.end("n1", status="completed", latency_ms=10)
    _reset_tracing()


def test_workflow_and_node_spans_when_enabled(monkeypatch):
    _reset_tracing()

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    tracing._provider = provider
    tracing._tracer = trace.get_tracer("aegis-test", "0.4.0")
    tracing._enabled = True

    with tracing.workflow_run_span("run-1", "wf-1", "Test Flow"):
        trace_id = tracing.get_trace_id()
        assert trace_id is not None

        tracker = tracing.NodeSpanTracker()
        tracker.start("agent-1", "agent", "Writer")
        tracker.end(
            "agent-1",
            status="completed",
            latency_ms=42,
            guardrail_status=None,
        )

    provider.force_flush()
    names = [span.name for span in exporter.get_finished_spans()]
    assert "workflow.run" in names
    assert "workflow.node" in names

    node_span = next(s for s in exporter.get_finished_spans() if s.name == "workflow.node")
    attrs = dict(node_span.attributes or {})
    assert attrs["node.id"] == "agent-1"
    assert attrs["node.type"] == "agent"
    assert attrs["node.latency_ms"] == 42

    _reset_tracing()


def test_parse_exporter_headers():
    assert tracing._parse_headers("") == {}
    assert tracing._parse_headers("Authorization=Bearer x, X-Key=abc") == {
        "Authorization": "Bearer x",
        "X-Key": "abc",
    }


def test_health_reports_tracing_disabled():
    from fastapi.testclient import TestClient

    from app.main import app

    _reset_tracing()
    tracing.init_tracing()

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["tracing_enabled"] is False

    _reset_tracing()