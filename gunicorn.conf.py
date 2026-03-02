import os


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    if value == "":
        return default
    return value


def _default_workers() -> int:
    cpu = os.cpu_count() or 1
    return (2 * cpu) + 1


bind = _env_str("KSRPC_GUNICORN_BIND", "0.0.0.0:8080")
worker_class = _env_str("KSRPC_GUNICORN_WORKER_CLASS", "aiohttp.GunicornWebWorker")
workers = _env_int("KSRPC_GUNICORN_WORKERS", _default_workers())
timeout = _env_int("KSRPC_GUNICORN_TIMEOUT", 120)
graceful_timeout = _env_int("KSRPC_GUNICORN_GRACEFUL_TIMEOUT", 30)
keepalive = _env_int("KSRPC_GUNICORN_KEEPALIVE", 15)
backlog = _env_int("KSRPC_GUNICORN_BACKLOG", 2048)
max_requests = _env_int("KSRPC_GUNICORN_MAX_REQUESTS", 10000)
max_requests_jitter = _env_int("KSRPC_GUNICORN_MAX_REQUESTS_JITTER", 1000)
accesslog = _env_str("KSRPC_GUNICORN_ACCESSLOG", "-")
errorlog = _env_str("KSRPC_GUNICORN_ERRORLOG", "-")
loglevel = _env_str("KSRPC_GUNICORN_LOGLEVEL", "info")
