#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import io
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType


def _find_repo_root() -> Path:
    script_path = Path(__file__).resolve()
    for candidate in (script_path.parent, *script_path.parents):
        if (candidate / "config_server.example.py").exists() and (candidate / "ksrpc" / "config_server.py").exists():
            return candidate
    return script_path.parents[2]


REPO_ROOT = _find_repo_root()
UPSTREAM_CONFIG_PATH = REPO_ROOT / "ksrpc" / "config_server.py"
LOCAL_CONFIG_PATH = REPO_ROOT / "config_server.example.py"
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"

REQUIRED_ENV_EXAMPLE_KEYS = {
    "OCI_IMAGE_REF",
    "KSRPC_CONTAINER_NAME",
    "KSRPC_HOST_PORT",
    "KSRPC_INSTANCES",
    "TUSHARE_TOKEN",
}

DISALLOWED_ENV_EXAMPLE_KEYS = {
    "KSRPC_CONFIG_PATH",
    "KSRPC_GUNICORN_BIND",
    "KSRPC_GUNICORN_CONFIG_PATH",
    "KSRPC_GUNICORN_WORKER_CLASS",
    "KSRPC_GUNICORN_WORKERS",
    "KSRPC_GUNICORN_TIMEOUT",
    "KSRPC_GUNICORN_GRACEFUL_TIMEOUT",
    "KSRPC_GUNICORN_KEEPALIVE",
    "KSRPC_GUNICORN_BACKLOG",
    "KSRPC_GUNICORN_MAX_REQUESTS",
    "KSRPC_GUNICORN_MAX_REQUESTS_JITTER",
    "GUNICORN_CMD_ARGS",
    "PORT",
    "CACHE_PATH",
    "USER_CREDENTIALS",
    "TIMESTAMP_CHECK",
    "IMPORT_RULES",
    "CACHE_ENABLE",
    "CACHE_TIMEOUT",
}

ENV_KEY_PATTERN = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _format_diff(name: str, target: str, missing: list[str], extra: list[str]) -> str:
    return (
        f"ERROR {name} {target} "
        f"missing={missing if missing else []} "
        f"extra={extra if extra else []}"
    )


def _load_module(path: Path, module_name: str) -> ModuleType:
    if not path.exists():
        raise FileNotFoundError(f"missing file: {_display_path(path)}")

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module spec: {_display_path(path)}")

    module = importlib.util.module_from_spec(spec)
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        spec.loader.exec_module(module)
    return module


def _public_uppercase_keys(module: ModuleType) -> set[str]:
    keys: set[str] = set()
    for key, value in vars(module).items():
        if key.startswith("_"):
            continue
        if not key.isupper():
            continue
        if callable(value):
            continue
        keys.add(key)
    return keys


def _read_env_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ENV_KEY_PATTERN.match(line)
        if match is not None:
            keys.add(match.group(1))
    return keys


def main() -> int:
    errors: list[str] = []

    try:
        upstream_module = _load_module(UPSTREAM_CONFIG_PATH, "_ksrpc_upstream_config_server")
        local_module = _load_module(LOCAL_CONFIG_PATH, "_ksrpc_local_config")
    except Exception as exc:
        print(f"ERROR load_module missing=[] extra=[{exc}]", file=sys.stderr)
        return 1

    upstream_keys = _public_uppercase_keys(upstream_module)
    local_keys = _public_uppercase_keys(local_module)

    config_missing = sorted(upstream_keys - local_keys)
    config_extra = sorted(local_keys - upstream_keys)
    if config_missing or config_extra:
        errors.append(
            _format_diff(
                "config_keys",
                "ksrpc/config_server.py_vs_config_server.example.py",
                config_missing,
                config_extra,
            )
        )

    if not ENV_EXAMPLE_PATH.exists():
        errors.append(
            _format_diff(
                "env_example_keys",
                _display_path(ENV_EXAMPLE_PATH),
                ["missing_file"],
                [],
            )
        )
    else:
        env_example_keys = _read_env_keys(ENV_EXAMPLE_PATH)
        env_example_missing = sorted(REQUIRED_ENV_EXAMPLE_KEYS - env_example_keys)
        if env_example_missing:
            errors.append(
                _format_diff(
                    "required_env_example_keys",
                    _display_path(ENV_EXAMPLE_PATH),
                    env_example_missing,
                    [],
                )
            )
        env_example_disallowed = sorted(env_example_keys & DISALLOWED_ENV_EXAMPLE_KEYS)
        if env_example_disallowed:
            errors.append(
                _format_diff(
                    "disallowed_env_example_keys",
                    _display_path(ENV_EXAMPLE_PATH),
                    [],
                    env_example_disallowed,
                )
            )

    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return 1

    print("OK check_config_drift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
