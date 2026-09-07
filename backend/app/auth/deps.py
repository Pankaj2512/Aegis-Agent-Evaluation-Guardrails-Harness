from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import Header, HTTPException, Query

from app.config import settings

DEFAULT_DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_API_KEY_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _resolve_api_token(
    authorization: str | None,
    x_aegis_api_key: str | None,
    api_key: str | None,
) -> str | None:
    token = x_aegis_api_key or api_key
    if not token and authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
    return token


def _api_key_user_map() -> dict[str, tuple[uuid.UUID, str]]:
    """Map api key -> (user_id, role). Values may be a bare uuid string or
    {"user_id": "...", "role": "viewer"|"editor"}."""
    raw = getattr(settings, "aegis_api_key_user_map", "") or ""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    mapping: dict[str, tuple[uuid.UUID, str]] = {}
    if isinstance(parsed, dict):
        for key, value in parsed.items():
            try:
                if isinstance(value, dict):
                    mapping[str(key)] = (
                        uuid.UUID(str(value.get("user_id"))),
                        str(value.get("role") or "editor").lower(),
                    )
                else:
                    mapping[str(key)] = (uuid.UUID(str(value)), "editor")
            except (ValueError, TypeError):
                continue
    return mapping


def user_id_from_api_key(token: str) -> uuid.UUID:
    mapped = _api_key_user_map().get(token)
    if mapped is not None:
        return mapped[0]
    if token == settings.aegis_api_key:
        return DEFAULT_DEV_USER_ID
    return uuid.uuid5(_API_KEY_NAMESPACE, token)


def role_from_api_key(token: str | None) -> str:
    if not token:
        return "editor"
    mapped = _api_key_user_map().get(token)
    return mapped[1] if mapped else "editor"


def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
    x_aegis_api_key: Annotated[str | None, Header(alias="X-Aegis-API-Key")] = None,
    api_key: Annotated[str | None, Query(alias="api_key")] = None,
) -> uuid.UUID:
    if not settings.auth_enabled:
        return DEFAULT_DEV_USER_ID

    token = _resolve_api_token(authorization, x_aegis_api_key, api_key)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Set X-Aegis-API-Key header or api_key query parameter.",
        )

    import hmac

    allowed = {settings.aegis_api_key, *_api_key_user_map().keys()}
    allowed.discard("")
    # Constant-time membership: compare against every allowed key so timing
    # does not leak which key (if any) matched.
    matched = False
    for candidate in allowed:
        if isinstance(candidate, str) and hmac.compare_digest(token, candidate):
            matched = True
    if not matched:
        raise HTTPException(status_code=401, detail="Invalid API key.")

    return user_id_from_api_key(token)