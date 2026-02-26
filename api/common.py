from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs, urlparse


def get_header(request: Any, key: str, default: str = "") -> str:
    headers = getattr(request, "headers", {}) or {}
    if isinstance(headers, dict):
        return headers.get(key, headers.get(key.lower(), default))
    return getattr(headers, "get", lambda *_: default)(key, default)


def get_query_param(request: Any, key: str, default: str) -> str:
    query = getattr(request, "query", None)
    if isinstance(query, dict):
        return str(query.get(key, default))

    query_params = getattr(request, "query_params", None)
    if query_params is not None:
        return str(query_params.get(key, default))

    url = getattr(request, "url", None)
    if url:
        parsed = urlparse(str(url))
        values = parse_qs(parsed.query).get(key)
        if values:
            return values[0]

    return default


def json_response(status: int, payload: dict[str, Any]) -> tuple[str, int, dict[str, str]]:
    return (
        json.dumps(payload, ensure_ascii=False),
        status,
        {"Content-Type": "application/json; charset=utf-8"},
    )
