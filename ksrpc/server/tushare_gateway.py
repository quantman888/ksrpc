from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests

from ksrpc.utils.tushare_meter import add_upstream_bytes

_DEFAULT_TIMEOUT = 25.0
_DEFAULT_HTTP_URL = "http://api.waditu.com/dataapi"


def _http_url() -> str:
    return os.getenv("TUSHARE_HTTP_URL", _DEFAULT_HTTP_URL).rstrip("/")


def _token() -> str:
    token = os.getenv("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TUSHARE_TOKEN is not configured")
    return token


def _default_timeout() -> float:
    return float(os.getenv("TUSHARE_TIMEOUT", str(_DEFAULT_TIMEOUT)))


def _normalize_fields(fields: Any) -> str:
    if fields is None:
        return ""
    if isinstance(fields, str):
        return fields
    if isinstance(fields, (list, tuple)):
        return ",".join(str(item) for item in fields if str(item).strip())
    return str(fields)


def _resolve_timeout(remaining_timeout_s: float | int | None) -> float:
    default_timeout = _default_timeout()
    if remaining_timeout_s is None:
        return default_timeout

    remaining = float(remaining_timeout_s)
    if remaining <= 1.0:
        raise TimeoutError("remaining timeout exhausted before upstream request")
    return min(default_timeout, remaining - 1.0)


def _build_payload(api_name: str, params: dict[str, Any], fields: str) -> dict[str, Any]:
    return {
        "api_name": api_name,
        "token": _token(),
        "params": params,
        "fields": fields,
    }


def _upstream_error_payload(result: dict[str, Any]) -> dict[str, Any]:
    try:
        code = int(result.get("code", -1))
    except (TypeError, ValueError):
        code = -1
    message = str(result.get("msg") or "upstream business error")
    return {"code": code, "msg": message}


def query(
    *,
    client_token: str,
    api_name: str,
    params: dict[str, Any] | None = None,
    fields: Any = "",
    remaining_timeout_s: float | int | None = None,
) -> dict[str, Any]:
    if not client_token:
        raise RuntimeError("client_token is required")
    if not api_name:
        raise RuntimeError("api_name is required")

    params = dict(params or {})
    fields_text = _normalize_fields(fields)
    timeout = _resolve_timeout(remaining_timeout_s)
    payload = _build_payload(api_name, params, fields_text)

    response = requests.post(f"{_http_url()}/{api_name}", json=payload, timeout=timeout)
    raw_body = response.content
    upstream_bytes = len(raw_body)
    quota_bytes_used_after = add_upstream_bytes(client_token, upstream_bytes)

    if not response.ok:
        text = response.text.strip() or f"upstream http {response.status_code}"
        raise RuntimeError(text)

    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError("invalid upstream response payload") from exc

    if not isinstance(result, dict):
        raise RuntimeError("invalid upstream response shape")

    if int(result.get("code", -1)) != 0:
        return {
            "upstream_error": _upstream_error_payload(result),
            "upstream_bytes": upstream_bytes,
            "quota_bytes_used_after": quota_bytes_used_after,
        }

    data = result.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("invalid upstream data payload")

    columns = list(data.get("fields") or [])
    items = list(data.get("items") or [])
    dataframe = pd.DataFrame(items, columns=columns)

    return {
        "dataframe": dataframe,
        "upstream_bytes": upstream_bytes,
        "quota_bytes_used_after": quota_bytes_used_after,
    }
