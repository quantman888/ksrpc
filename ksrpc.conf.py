import json
import os


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name, "")
    if value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name, "")
    if value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_json_dict(name: str, default: dict) -> dict:
    raw = os.getenv(name, "").strip()
    if raw == "":
        return default
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return default
    if not isinstance(loaded, dict):
        return default
    return loaded


# Web server config
HOST = os.getenv("KSRPC_HOST", "0.0.0.0")
PORT = _env_int("KSRPC_PORT", 8080)
PATH = os.getenv("KSRPC_PATH", "/api/v1")
TIMESTAMP_CHECK = _env_bool("KSRPC_TIMESTAMP_CHECK", True)


# Basic auth config
basic_user = os.getenv("KSRPC_BASIC_USER", "").strip()
basic_password = os.getenv("KSRPC_BASIC_PASSWORD", "")
if basic_user:
    USER_CREDENTIALS = {basic_user: basic_password}
else:
    USER_CREDENTIALS = _env_json_dict(
        "KSRPC_BASIC_CREDENTIALS_JSON",
        {
            "admin": "change_me_now",
        },
    )


# Import allowlist
IMPORT_RULES = _env_json_dict(
    "KSRPC_IMPORT_RULES_JSON",
    {
        "ksrpc.server.tushare": True,
        "ksrpc.server.demo": False,
        "tushare": False,
        "ksrpc.server.*": False,
        "builtins": False,
        "*": False,
    },
)


# File cache config
CACHE_ENABLE = _env_bool("KSRPC_CACHE_ENABLE", False)
CACHE_PATH = os.getenv("KSRPC_CACHE_PATH", "/opt/ksrpc/cache")
CACHE_TIMEOUT = {}
for key, value in _env_json_dict(
    "KSRPC_CACHE_TIMEOUT_JSON",
    {
        "ksrpc.server.tushare.daily": 30,
        "ksrpc.server.tushare.*": 60,
        "*": 600,
    },
).items():
    try:
        CACHE_TIMEOUT[str(key)] = int(value)
    except (TypeError, ValueError):
        continue
if not CACHE_TIMEOUT:
    CACHE_TIMEOUT = {"*": 600}


print(__file__)
