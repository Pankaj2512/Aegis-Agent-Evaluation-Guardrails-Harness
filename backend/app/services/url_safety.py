from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata.goog",
    }
)


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
    )


def _hostname_blocked(hostname: str) -> bool:
    host = hostname.lower().rstrip(".")
    return host in BLOCKED_HOSTNAMES or host.endswith(".local") or host.endswith(".internal")


def _validate_resolved_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, label: str) -> None:
    if _is_blocked_ip(ip):
        raise ValueError(f"{label} resolves to blocked address: {ip}")


def validate_hostname_public(hostname: str, port: int = 443) -> None:
    """Ensure a hostname does not resolve to private or local addresses."""
    if not hostname:
        raise ValueError("Hostname is required")

    if _hostname_blocked(hostname):
        raise ValueError(f"Hostname '{hostname}' is not allowed")

    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None

    if literal is not None:
        _validate_resolved_ip(literal, f"Host '{hostname}'")
        return

    resolved_any = False
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            infos = socket.getaddrinfo(hostname, port, family, socket.SOCK_STREAM)
        except socket.gaierror:
            continue
        for info in infos:
            resolved_any = True
            resolved = ipaddress.ip_address(info[4][0])
            _validate_resolved_ip(resolved, f"Hostname '{hostname}'")

    if not resolved_any:
        raise ValueError(f"Hostname '{hostname}' could not be resolved")


def resolve_public_ip(hostname: str, port: int) -> str:
    """Resolve hostname once and return the first public IP address."""
    validate_hostname_public(hostname, port)

    try:
        literal = ipaddress.ip_address(hostname)
        return str(literal)
    except ValueError:
        pass

    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            infos = socket.getaddrinfo(hostname, port, family, socket.SOCK_STREAM)
        except socket.gaierror:
            continue
        for info in infos:
            resolved = ipaddress.ip_address(info[4][0])
            if not _is_blocked_ip(resolved):
                return str(resolved)

    raise ValueError(f"Hostname '{hostname}' could not be resolved to a public address")


def validate_http_url(url: str) -> str:
    """Reject URLs that target private networks or local services (SSRF mitigation)."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("HTTP tool only supports http:// and https:// URLs")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("HTTP URL must include a hostname")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    validate_hostname_public(hostname, port)
    return url


def _url_with_pinned_host(parsed, ip: str, port: int) -> str:
    hostpart = f"[{ip}]" if ":" in ip else ip
    default_port = 443 if parsed.scheme == "https" else 80
    netloc = f"{hostpart}:{port}" if port != default_port else hostpart
    return urlunparse(
        (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
    )


async def safe_http_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    content: bytes | None = None,
    max_redirects: int = 5,
    max_body_bytes: int | None = None,
) -> httpx.Response:
    """HTTP request with DNS pinning to prevent TOCTOU rebinding attacks.

    When ``max_body_bytes`` is set the response body is streamed and truncated
    so a huge payload cannot exhaust process memory before the caller slices it.
    """
    # validate_http_url / resolve_public_ip do blocking socket.getaddrinfo —
    # keep the event loop free by running the DNS work off-thread.
    current_url = await asyncio.to_thread(validate_http_url, url)
    current_method = method.upper()
    body = content
    redirects = 0

    while True:
        parsed = urlparse(current_url)
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("HTTP URL must include a hostname")

        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        resolved_ip = await asyncio.to_thread(resolve_public_ip, hostname, port)
        pinned_url = _url_with_pinned_host(parsed, resolved_ip, port)

        request_headers = dict(headers or {})
        request_headers.setdefault("Host", hostname)

        if max_body_bytes is not None:
            async with client.stream(
                current_method,
                pinned_url,
                headers=request_headers,
                content=body,
                follow_redirects=False,
            ) as response:
                if (
                    response.status_code in {301, 302, 303, 307, 308}
                    and redirects < max_redirects
                ):
                    location = response.headers.get("location")
                    await response.aread()
                    if not location:
                        # Build a fully-buffered response for the caller.
                        return await client.request(
                            current_method,
                            pinned_url,
                            headers=request_headers,
                            content=body,
                            follow_redirects=False,
                        )
                    redirects += 1
                    current_url = await asyncio.to_thread(
                        validate_http_url, urljoin(current_url, location)
                    )
                    if response.status_code == 303:
                        current_method = "GET"
                        body = None
                    continue
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    if not chunk:
                        continue
                    remain = max_body_bytes - total
                    if remain <= 0:
                        break
                    if len(chunk) > remain:
                        chunks.append(chunk[:remain])
                        total += remain
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                # Materialize a Response the caller can treat like a normal one.
                return httpx.Response(
                    status_code=response.status_code,
                    headers=response.headers,
                    content=b"".join(chunks),
                    request=response.request,
                )

        response = await client.request(
            current_method,
            pinned_url,
            headers=request_headers,
            content=body,
            follow_redirects=False,
        )

        if response.status_code not in {301, 302, 303, 307, 308} or redirects >= max_redirects:
            return response

        location = response.headers.get("location")
        if not location:
            return response

        current_url = await asyncio.to_thread(
            validate_http_url, urljoin(current_url, location)
        )
        if response.status_code in {301, 302, 303}:
            current_method = "GET"
            body = None
        redirects += 1