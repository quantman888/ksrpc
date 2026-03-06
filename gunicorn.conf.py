import os


# ---------------------------------------------------------------------
# 需维护区（仅以下内容需要人工关注）
# ---------------------------------------------------------------------
# workers 动态默认策略：2 * CPU + 1
_WORKERS_DEFAULT_SENTINEL = "__DEFAULT_WORKERS__"

# Gunicorn 配置项默认值（未配置环境变量时生效）
_FALLBACK_DEFAULTS = {
    "bind": "0.0.0.0:8080",
    "worker_class": "aiohttp.GunicornWebWorker",
    "workers": _WORKERS_DEFAULT_SENTINEL,
    "timeout": 120,
    "graceful_timeout": 30,
    "keepalive": 15,
    "backlog": 2048,
    "max_requests": 10000,
    "max_requests_jitter": 1000,
    "accesslog": "-",
    "errorlog": "-",
    "loglevel": "info",
}

# Gunicorn 配置项与环境变量映射规则
# type 支持: str, int
_ENV_RULES = {
    "bind": {"env": "KSRPC_GUNICORN_BIND", "type": "str"},
    "worker_class": {"env": "KSRPC_GUNICORN_WORKER_CLASS", "type": "str"},
    "workers": {"env": "KSRPC_GUNICORN_WORKERS", "type": "int"},
    "timeout": {"env": "KSRPC_GUNICORN_TIMEOUT", "type": "int"},
    "graceful_timeout": {"env": "KSRPC_GUNICORN_GRACEFUL_TIMEOUT", "type": "int"},
    "keepalive": {"env": "KSRPC_GUNICORN_KEEPALIVE", "type": "int"},
    "backlog": {"env": "KSRPC_GUNICORN_BACKLOG", "type": "int"},
    "max_requests": {"env": "KSRPC_GUNICORN_MAX_REQUESTS", "type": "int"},
    "max_requests_jitter": {"env": "KSRPC_GUNICORN_MAX_REQUESTS_JITTER", "type": "int"},
    "accesslog": {"env": "KSRPC_GUNICORN_ACCESSLOG", "type": "str"},
    "errorlog": {"env": "KSRPC_GUNICORN_ERRORLOG", "type": "str"},
    "loglevel": {"env": "KSRPC_GUNICORN_LOGLEVEL", "type": "str"},
}

# 导出顺序固定，便于维护审查
_EXPORT_KEYS = tuple(_ENV_RULES.keys())


# ---------------------------------------------------------------------
# 0维护区（运行时同步逻辑，通常无需人工维护）
# ---------------------------------------------------------------------
def _default_workers() -> int:
    cpu = os.cpu_count() or 1
    return (2 * cpu) + 1


def _resolve_default(option_name: str):
    value = _FALLBACK_DEFAULTS[option_name]
    if value == _WORKERS_DEFAULT_SENTINEL:
        return _default_workers()
    return value


def _coerce_str(raw: str, default: str) -> str:
    text = raw.strip()
    if text == "":
        return default
    return text


def _coerce_int(raw: str, default: int) -> int:
    text = raw.strip()
    if text == "":
        return default
    try:
        return int(text)
    except ValueError:
        return default


_PARSERS = {
    "str": _coerce_str,
    "int": _coerce_int,
}


for _key in _EXPORT_KEYS:
    _rule = _ENV_RULES[_key]
    _raw = os.getenv(_rule["env"], "")
    _default = _resolve_default(_key)
    _parser = _PARSERS.get(_rule["type"], _coerce_str)
    globals()[_key] = _parser(_raw, _default)
