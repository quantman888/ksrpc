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
        if (candidate / "ksrpc.conf.py").exists() and (candidate / "ksrpc" / "config_server.py").exists():
            return candidate
    return script_path.parents[2]


REPO_ROOT = _find_repo_root()
UPSTREAM_CONFIG_PATH = REPO_ROOT / "ksrpc" / "config_server.py"
LOCAL_CONFIG_PATH = REPO_ROOT / "ksrpc.conf.py"
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"

ALLOWED_EXTRA_KEYS = {"TUSHARE_TIMEOUT"}
DEPRECATED_SERVICE_ALIAS_KEYS = {
    "KSRPC_BASIC_CREDENTIALS_JSON",
    "KSRPC_BASIC_PASSWORD",
    "KSRPC_BASIC_USER",
    "KSRPC_CACHE_ENABLE",
    "KSRPC_CACHE_PATH",
    "KSRPC_CACHE_TIMEOUT_JSON",
    "KSRPC_HOST",
    "KSRPC_IMPORT_RULES_JSON",
    "KSRPC_PATH",
    "KSRPC_PATH_HTTP",
    "KSRPC_PATH_WS",
    "KSRPC_PORT",
    "KSRPC_TIMESTAMP_CHECK",
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

    # Ensure ksrpc.conf.py resolves local package when it introspects upstream defaults.
    sys.path.insert(0, str(REPO_ROOT))

    try:
        upstream_module = _load_module(UPSTREAM_CONFIG_PATH, "_ksrpc_upstream_config_server")
        local_module = _load_module(LOCAL_CONFIG_PATH, "_ksrpc_local_config")
    except Exception as exc:
        print(f"ERROR load_module missing=[] extra=[{exc}]", file=sys.stderr)
        return 1

    upstream_keys = _public_uppercase_keys(upstream_module)
    local_keys = _public_uppercase_keys(local_module)

    config_missing = sorted(upstream_keys - local_keys)
    config_extra = sorted((local_keys - upstream_keys) - ALLOWED_EXTRA_KEYS)
    if config_missing or config_extra:
        errors.append(
            _format_diff(
                "config_keys",
                "ksrpc/config_server.py_vs_ksrpc.conf.py",
                config_missing,
                config_extra,
            )
        )

    extra_rules = getattr(local_module, "_EXTRA_ENV_RULES", {})
    if isinstance(extra_rules, dict):
        extra_rule_keys = {k for k in extra_rules if isinstance(k, str)}
        non_whitelisted = sorted(extra_rule_keys - ALLOWED_EXTRA_KEYS)
        if non_whitelisted:
            errors.append(
                _format_diff(
                    "extra_key_whitelist",
                    "ksrpc.conf.py._EXTRA_ENV_RULES",
                    [],
                    non_whitelisted,
                )
            )
    else:
        errors.append(
            _format_diff(
                "extra_key_whitelist",
                "ksrpc.conf.py._EXTRA_ENV_RULES",
                [],
                ["_EXTRA_ENV_RULES_not_dict"],
            )
        )

    fallback_defaults = getattr(local_module, "_FALLBACK_DEFAULTS", None)
    if not isinstance(fallback_defaults, dict):
        errors.append(
            _format_diff(
                "fallback_defaults",
                "ksrpc.conf.py._FALLBACK_DEFAULTS",
                sorted(upstream_keys),
                ["_FALLBACK_DEFAULTS_not_dict"],
            )
        )
    else:
        fallback_keys = {k for k in fallback_defaults if isinstance(k, str)}
        fallback_missing = sorted(upstream_keys - fallback_keys)
        fallback_extra = sorted(fallback_keys - upstream_keys)
        if fallback_missing or fallback_extra:
            errors.append(
                _format_diff(
                    "fallback_defaults",
                    "ksrpc.conf.py._FALLBACK_DEFAULTS",
                    fallback_missing,
                    fallback_extra,
                )
            )

    if not ENV_EXAMPLE_PATH.exists():
        errors.append(
            _format_diff(
                "deprecated_alias_keys",
                _display_path(ENV_EXAMPLE_PATH),
                ["missing_file"],
                [],
            )
        )
    else:
        env_example_keys = _read_env_keys(ENV_EXAMPLE_PATH)
        env_example_aliases = sorted(env_example_keys & DEPRECATED_SERVICE_ALIAS_KEYS)
        if env_example_aliases:
            errors.append(
                _format_diff(
                    "deprecated_alias_keys",
                    _display_path(ENV_EXAMPLE_PATH),
                    [],
                    env_example_aliases,
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
