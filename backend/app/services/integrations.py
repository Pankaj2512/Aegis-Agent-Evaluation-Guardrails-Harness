"""Integration node handlers — Slack, Email, Postgres (n8n-style)."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import re
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

import json as json_module

from app.http_client import get_http_client
from app.services.expressions import render_template
from app.services.url_safety import (
    resolve_public_ip,
    safe_http_request,
    validate_hostname_public,
    validate_http_url,
)

logger = logging.getLogger("aegis.integrations")

MAX_EMAIL_BODY = 10_000
MAX_PG_ROWS = 50
_SINGLE_EMAIL_RE = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")
_READ_ONLY_SQL = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


async def _post_integration_webhook(webhook_url: str, payload: dict[str, Any]) -> str:
    validate_http_url(webhook_url)
    client = get_http_client()
    response = await safe_http_request(
        client,
        "POST",
        webhook_url,
        headers={"Content-Type": "application/json"},
        content=json_module.dumps(payload).encode("utf-8"),
    )
    return str(response.status_code)


async def run_discord_integration(
    webhook_url: str,
    message_template: str,
    context: dict[str, Any],
    node_input: str,
) -> str:
    message = render_template(message_template or "{{last_output}}", context, node_input)
    try:
        body = await _post_integration_webhook(webhook_url, {"content": message[:2000]})
        return f"Discord {body}"
    except Exception as exc:
        return f"Discord error: {exc}"


async def run_slack_integration(
    webhook_url: str,
    message_template: str,
    context: dict[str, Any],
    node_input: str,
) -> str:
    message = render_template(message_template or "{{last_output}}", context, node_input)
    try:
        body = await _post_integration_webhook(webhook_url, {"text": message})
        return f"Slack {body}"
    except Exception as exc:
        return f"Slack error: {exc}"


def _validate_single_email_recipient(to_addr: str) -> str | None:
    """Return an error message when the recipient is invalid; None if acceptable."""
    address = to_addr.strip()
    if not address:
        return "Email error: missing 'to' address in credential config"
    if "," in address or ";" in address:
        return "Email error: multiple recipients not allowed"
    if not _SINGLE_EMAIL_RE.match(address):
        return "Email error: invalid 'to' address"
    return None


async def run_email_integration(
    config: dict[str, Any],
    subject_template: str,
    body_template: str,
    context: dict[str, Any],
    node_input: str,
) -> str:
    subject = render_template(subject_template or "Aegis notification", context, node_input)
    body = render_template(body_template or "{{last_output}}", context, node_input)[:MAX_EMAIL_BODY]
    to_addr = render_template(str(config.get("to") or ""), context, node_input)
    from_addr = config.get("from") or config.get("smtp_user") or "noreply@aegis.local"

    recipient_error = _validate_single_email_recipient(to_addr)
    if recipient_error:
        return recipient_error

    # MVP: log-style delivery when SMTP is not configured
    if not config.get("smtp_host"):
        logger.info(
            "Email queued without SMTP",
            extra={"to": to_addr, "subject_length": len(subject)},
        )
        return "Email queued (SMTP not configured)"

    try:
        import smtplib
        from email.message import EmailMessage

        def _send() -> None:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = from_addr
            msg["To"] = to_addr
            msg.set_content(body)

            host = config["smtp_host"]
            port = int(config.get("smtp_port") or 587)
            user = config.get("smtp_user")
            password = config.get("smtp_password")

            with smtplib.SMTP(host, port, timeout=15) as server:
                server.starttls()
                if user and password:
                    server.login(user, password)
                server.send_message(msg)

        await asyncio.to_thread(_send)
        return f"Email sent to {to_addr}"
    except Exception as exc:
        return f"Email error: {exc}"


def _validate_postgres_connection_url(connection_url: str) -> str:
    """Validate the URL targets a public Postgres host and return the pinned IP.

    Returns the resolved public IP so the caller can connect to *that* address
    (libpq ``hostaddr``) instead of re-resolving — closing the DNS-rebinding
    TOCTOU window the HTTP path already guards against (audit P2-13).
    """
    parsed = make_url(connection_url)
    driver = (parsed.drivername or "").split("+", 1)[0]
    if driver not in {"postgresql", "postgres"}:
        raise ValueError("Only PostgreSQL connection URLs are allowed")
    host = parsed.host
    if not host:
        raise ValueError("Postgres connection URL must include a hostname")
    port = parsed.port or 5432
    validate_hostname_public(host, port)
    return resolve_public_ip(host, port)


_PG_ENGINES: dict[str, Engine] = {}
_TEMPLATE_PLACEHOLDER = re.compile(r"\{\{([^}]+)\}\}")


def clear_pg_engine_for_url(connection_url: str) -> None:
    """Dispose and evict a cached Postgres engine (e.g. after credential delete)."""
    engine = _PG_ENGINES.pop(connection_url, None)
    if engine is not None:
        engine.dispose()


def _pg_engine(connection_url: str) -> Engine:
    pinned_ip = _validate_postgres_connection_url(connection_url)
    cached = _PG_ENGINES.get(connection_url)
    if cached is not None:
        return cached
    # Pin the connection to the validated IP via libpq ``hostaddr`` (the URL's
    # hostname is still used for TLS/SNI and auth), so a rebind after validation
    # cannot redirect the socket to a private address.
    connect_args: dict[str, Any] = {}
    parsed = make_url(connection_url)
    host = parsed.host or ""
    try:
        ipaddress.ip_address(host)
        is_literal = True
    except ValueError:
        is_literal = False
    if pinned_ip and not is_literal:
        connect_args = {"hostaddr": pinned_ip}
    engine = create_engine(
        connection_url, pool_pre_ping=True, connect_args=connect_args
    )
    _PG_ENGINES[connection_url] = engine
    return engine


def _parameterize_query(
    query_template: str,
    context: dict[str, Any],
    node_input: str,
) -> tuple[str, dict[str, str]]:
    binds: dict[str, str] = {}
    counter = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal counter
        token = match.group(0)
        value = str(render_template(token, context, node_input))
        key = f"p{counter}"
        counter += 1
        binds[key] = value
        return f":{key}"

    query = _TEMPLATE_PLACEHOLDER.sub(replace, query_template).strip()
    if ";" in query:
        raise ValueError("Semicolons are not allowed in Postgres queries")
    return query, binds


async def run_postgres_integration(
    config: dict[str, Any],
    query_template: str,
    context: dict[str, Any],
    node_input: str,
) -> str:
    connection_url = config.get("connection_url")
    if not connection_url:
        return "Postgres error: missing connection_url in credential"

    try:
        query, binds = _parameterize_query(query_template or "SELECT 1", context, node_input)
    except ValueError as exc:
        return f"Postgres error: {exc}"

    if not _READ_ONLY_SQL.match(query):
        return "Postgres error: only read-only SELECT/WITH queries are allowed"

    try:
        # _pg_engine runs blocking socket.getaddrinfo (validation + IP pin);
        # build/resolve the engine inside the worker thread so DNS never blocks
        # the event loop (audit P2-20).
        def _run() -> list[dict[str, Any]]:
            engine = _pg_engine(connection_url)
            with engine.connect() as conn:
                with conn.begin():
                    conn.execute(text("SET TRANSACTION READ ONLY"))
                    result = conn.execute(text(query), binds)
                    rows = result.mappings().fetchmany(MAX_PG_ROWS)
                    return [dict(row) for row in rows]

        rows = await asyncio.to_thread(_run)
        return json.dumps({"rows": rows, "count": len(rows)}, default=str, ensure_ascii=False)
    except Exception as exc:
        return f"Postgres error: {exc}"