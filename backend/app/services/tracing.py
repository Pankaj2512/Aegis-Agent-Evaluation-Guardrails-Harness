"""OpenTelemetry tracing for workflow execution and HTTP requests."""

from __future__ import annotations

import logging
import random
from contextlib import contextmanager
from typing import Any, Generator

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, StatusCode

logger = logging.getLogger("aegis.tracing")

_tracer: trace.Tracer | None = None
_provider: TracerProvider | None = None
_enabled = False


def is_tracing_enabled() -> bool:
    return _enabled


def _parse_headers(raw: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for part in raw.split(","):
        piece = part.strip()
        if not piece or "=" not in piece:
            continue
        key, value = piece.split("=", 1)
        headers[key.strip()] = value.strip()
    return headers


def init_tracing() -> None:
    global _tracer, _provider, _enabled

    from app.config import settings

    if not settings.otel_enabled:
        _enabled = False
        return

    if not settings.otel_exporter_endpoint:
        logger.warning(
            "otel_enabled is true but otel_exporter_endpoint is empty; tracing disabled"
        )
        _enabled = False
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": "0.4.0",
        }
    )
    exporter_kwargs: dict[str, Any] = {"endpoint": settings.otel_exporter_endpoint}
    headers = _parse_headers(settings.otel_exporter_headers)
    if headers:
        exporter_kwargs["headers"] = headers

    exporter = OTLPSpanExporter(**exporter_kwargs)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _provider = provider
    _tracer = trace.get_tracer("aegis", "0.4.0")
    _enabled = True
    logger.info(
        "OpenTelemetry tracing enabled",
        extra={
            "event": "tracing_init",
            "endpoint": settings.otel_exporter_endpoint,
            "service": settings.otel_service_name,
        },
    )


def shutdown_tracing() -> None:
    global _tracer, _provider, _enabled

    if _provider is not None:
        _provider.shutdown()
    _provider = None
    _tracer = None
    _enabled = False


def get_trace_id() -> str | None:
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if not ctx.is_valid:
        return None
    return format(ctx.trace_id, "032x")


def _should_sample() -> bool:
    from app.config import settings

    rate = max(0.0, min(1.0, settings.otel_sample_rate))
    if rate >= 1.0:
        return True
    if rate <= 0.0:
        return False
    return random.random() < rate


@contextmanager
def workflow_run_span(
    run_id: str,
    workflow_id: str | None,
    workflow_name: str | None,
) -> Generator[Span | None, None, None]:
    if not _enabled or _tracer is None or not _should_sample():
        yield None
        return

    with _tracer.start_as_current_span(
        "workflow.run",
        attributes={
            "run.id": run_id,
            "workflow.id": workflow_id or "",
            "workflow.name": workflow_name or "",
        },
    ) as span:
        yield span


class NodeSpanTracker:
    """Tracks in-flight ADK node spans for a single workflow run."""

    def __init__(self) -> None:
        self._spans: dict[str, Span] = {}

    def start(self, node_id: str, node_type: str, node_label: str) -> None:
        from app.config import settings

        if not _enabled or _tracer is None or not settings.otel_node_spans:
            return
        span = _tracer.start_span(
            "workflow.node",
            attributes={
                "node.id": node_id,
                "node.type": node_type,
                "node.label": node_label,
            },
        )
        self._spans[node_id] = span

    def set_gen_ai_usage(self, node_id: str, usage: dict) -> None:
        """Attach OTel gen_ai semantic-convention attributes to a node span."""
        span = self._spans.get(node_id)
        if span is None:
            return
        model = usage.get("model")
        if model:
            span.set_attribute("gen_ai.request.model", str(model))
            span.set_attribute("gen_ai.response.model", str(model))
        if usage.get("prompt_tokens") is not None:
            span.set_attribute("gen_ai.usage.input_tokens", int(usage["prompt_tokens"]))
        if usage.get("completion_tokens") is not None:
            span.set_attribute("gen_ai.usage.output_tokens", int(usage["completion_tokens"]))
        if usage.get("cost_usd") is not None:
            span.set_attribute("gen_ai.usage.cost_usd", float(usage["cost_usd"]))

    def end(
        self,
        node_id: str,
        *,
        status: str,
        latency_ms: int,
        guardrail_status: str | None = None,
        error: str | None = None,
    ) -> None:
        span = self._spans.pop(node_id, None)
        if span is None:
            return

        span.set_attribute("node.status", status)
        span.set_attribute("node.latency_ms", latency_ms)
        if guardrail_status:
            span.set_attribute("node.guardrail_status", guardrail_status)
        if error:
            span.set_status(StatusCode.ERROR, error)
        elif status == "failed":
            span.set_status(StatusCode.ERROR, f"node {node_id} failed")
        else:
            span.set_status(StatusCode.OK)
        span.end()


def install_http_middleware(app: Any) -> None:
    from starlette.requests import Request

    @app.middleware("http")
    async def otel_http_middleware(request: Request, call_next):
        if not _enabled or _tracer is None:
            return await call_next(request)

        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        span_name = f"{request.method} {route_path}"

        with _tracer.start_as_current_span(
            span_name,
            kind=trace.SpanKind.SERVER,
            attributes={
                "http.method": request.method,
                "http.route": route_path,
                "http.target": request.url.path,
            },
        ) as span:
            response = await call_next(request)
            span.set_attribute("http.status_code", response.status_code)
            if response.status_code >= 500:
                span.set_status(StatusCode.ERROR)
            return response