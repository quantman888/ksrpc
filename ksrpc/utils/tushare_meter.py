from __future__ import annotations

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import redis

_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_REDIS_CLIENT: redis.Redis | None = None


def _redis_url() -> str:
    url = os.getenv("TUSHARE_GATEWAY_REDIS_URL", "").strip()
    if not url:
        raise RuntimeError("TUSHARE_GATEWAY_REDIS_URL is not configured")
    return url


def _redis_key_prefix() -> str:
    return os.getenv("TUSHARE_GATEWAY_REDIS_KEY_PREFIX", "ksrpc:tushare:gateway:dev").strip()


def get_redis_client() -> redis.Redis:
    global _REDIS_CLIENT
    if _REDIS_CLIENT is None:
        _REDIS_CLIENT = redis.Redis.from_url(_redis_url(), decode_responses=True)
    return _REDIS_CLIENT


def shanghai_now() -> datetime:
    return datetime.now(_SHANGHAI_TZ)


def shanghai_day_key(now: datetime | None = None) -> str:
    current = now or shanghai_now()
    return current.strftime("%Y%m%d")


def quota_key(client_token: str, *, now: datetime | None = None) -> str:
    day_key = shanghai_day_key(now=now)
    prefix = _redis_key_prefix()
    return f"{prefix}:quota:{day_key}:{client_token}"


def quota_expire_at(now: datetime | None = None) -> int:
    current = now or shanghai_now()
    next_midnight = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    # 保留到下一自然日之后，便于排查与对账。
    keep_until = next_midnight + timedelta(days=2)
    return int(keep_until.timestamp())


def add_upstream_bytes(client_token: str, upstream_bytes: int) -> int:
    if not client_token:
        raise RuntimeError("client_token is required for metering")
    if upstream_bytes < 0:
        raise RuntimeError("upstream_bytes must be >= 0")

    client = get_redis_client()
    key = quota_key(client_token)
    total = client.incrby(key, upstream_bytes)
    client.expireat(key, quota_expire_at())
    return int(total)


def get_upstream_bytes(client_token: str) -> int:
    if not client_token:
        raise RuntimeError("client_token is required for metering")

    client = get_redis_client()
    raw = client.get(quota_key(client_token))
    return int(raw or 0)
