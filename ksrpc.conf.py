import importlib.util
import io
import json
import os
import sys
import types
from importlib import import_module
from pathlib import Path
from contextlib import redirect_stdout


# ---------------------------------------------------------------------
# 需维护区（仅以下内容需要人工关注）
# ---------------------------------------------------------------------
# docker-limited 受限实例模块名（客户端使用 RpcClient 调用）
_LIMITED_MODULE_NAME = "ksrpc.server.tushare_opt_mins"

# docker-limited 硬切换规则：仅允许受限模块，其他一律拒绝
_LOCKED_IMPORT_RULES = {
    "ksrpc.server.tushare_opt_mins": True,
    "ksrpc.server.tushare": False,
    "ksrpc.server.demo": False,
    "tushare": False,
    "ksrpc.server.*": False,
    "builtins": False,
    "*": False,
}

# 兜底默认项：仅在上游 config_server.py 无法加载时使用。
_FALLBACK_DEFAULTS = {
    "PORT": 8080,
    "HOST": None,
    "PATH": "/api/v1",
    "USER_CREDENTIALS": {"admin": "change_me_now"},
    "TIMESTAMP_CHECK": 30,
    "IMPORT_RULES": dict(_LOCKED_IMPORT_RULES),
    "CACHE_ENABLE": False,
    "CACHE_PATH": "/opt/ksrpc/cache",
    "CACHE_TIMEOUT": {
        "ksrpc.server.tushare.daily": 30,
        "ksrpc.server.tushare.*": 60,
        "*": 600,
    },
}

# 环境变量冲突策略：避免误读系统 PATH。
_SKIP_ENV_KEYS = {"PATH"}

# 后处理规则：把需要显式维护的键名集中到这里，底部逻辑不再写死变量名。
# kind:
# - str_dict: 规范化为 {str: str}
# - int_dict: 规范化为 {str: int}
_POST_NORMALIZE_RULES = {
    "USER_CREDENTIALS": {"kind": "str_dict", "fallback": {"admin": "change_me_now"}},
    "CACHE_TIMEOUT": {"kind": "int_dict", "fallback": {"*": 600}},
}

# 额外扩展环境变量规则：不在上游 config_server.py 中的可选键。
# parser:
# - float: 解析失败则忽略该键
_EXTRA_ENV_RULES = {
    "TUSHARE_TIMEOUT": {"parser": "float"},
}

# 导出策略：仅导出全大写键。
_EXPORT_UPPERCASE_ONLY = True


# ---------------------------------------------------------------------
# 0维护区（运行时同步逻辑，通常无需人工维护）
# ---------------------------------------------------------------------
_TRUE_VALUES = {"1", "true", "yes", "on", "y", "t"}
_FALSE_VALUES = {"0", "false", "no", "off", "n", "f"}


def _install_limited_tushare_module():
    """
    在配置加载阶段注入受限模块，仅暴露 opt_mins。
    不改 ksrpc 源码，靠 sys.modules 注册实现。
    """
    if _LIMITED_MODULE_NAME in sys.modules:
        return

    limited_module = types.ModuleType(_LIMITED_MODULE_NAME)
    limited_module.__file__ = __file__
    limited_module.__package__ = "ksrpc.server"
    limited_module.__all__ = ["opt_mins"]

    def opt_mins(*args, **kwargs):
        src_module = import_module("ksrpc.server.tushare")
        if not hasattr(src_module, "opt_mins"):
            raise AttributeError("ksrpc.server.tushare.opt_mins not found")
        return src_module.opt_mins(*args, **kwargs)

    limited_module.opt_mins = opt_mins
    sys.modules[_LIMITED_MODULE_NAME] = limited_module


def _load_upstream_defaults() -> dict:
    try:
        pkg_spec = importlib.util.find_spec("ksrpc")
        if pkg_spec is None or pkg_spec.origin is None:
            return dict(_FALLBACK_DEFAULTS)

        default_path = Path(pkg_spec.origin).resolve().parent / "config_server.py"
        if not default_path.exists():
            return dict(_FALLBACK_DEFAULTS)

        if default_path.resolve() == Path(__file__).resolve():
            return dict(_FALLBACK_DEFAULTS)

        spec = importlib.util.spec_from_file_location("_ksrpc_builtin_config_server", default_path)
        if spec is None or spec.loader is None:
            return dict(_FALLBACK_DEFAULTS)

        module = importlib.util.module_from_spec(spec)
        with redirect_stdout(io.StringIO()):
            spec.loader.exec_module(module)
    except Exception:
        return dict(_FALLBACK_DEFAULTS)

    defaults = {}
    for key, value in vars(module).items():
        if not key.isupper():
            continue
        if callable(value):
            continue
        defaults[key] = value

    if not defaults:
        return dict(_FALLBACK_DEFAULTS)
    return defaults


def _coerce_bool(raw: str, default: bool) -> bool:
    text = raw.strip().lower()
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    return default


def _coerce_json_dict(raw: str, default: dict) -> dict:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return default
    if not isinstance(value, dict):
        return default
    return value


def _coerce_by_default_type(raw: str, default):
    if isinstance(default, bool):
        return _coerce_bool(raw, default)
    if isinstance(default, int) and not isinstance(default, bool):
        try:
            return int(raw)
        except ValueError:
            return default
    if isinstance(default, float):
        try:
            return float(raw)
        except ValueError:
            return default
    if isinstance(default, dict):
        return _coerce_json_dict(raw, default)
    if isinstance(default, list):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return default
        return value if isinstance(value, list) else default
    if default is None:
        return raw
    return raw


def _normalize_str_dict(value: dict, fallback: dict) -> dict:
    if not isinstance(value, dict):
        return fallback
    out = {}
    for k, v in value.items():
        out[str(k)] = str(v)
    return out or fallback


def _normalize_int_dict(value: dict, fallback: dict) -> dict:
    if not isinstance(value, dict):
        return fallback
    out = {}
    for k, v in value.items():
        try:
            out[str(k)] = int(v)
        except (TypeError, ValueError):
            continue
    return out or fallback


_install_limited_tushare_module()

_DEFAULT_CONFIG = _load_upstream_defaults()
_CONFIG = dict(_DEFAULT_CONFIG)

for _key, _default in _DEFAULT_CONFIG.items():
    if _key in _SKIP_ENV_KEYS:
        # 不读取进程 PATH，避免继承系统搜索路径而污染服务路由 PATH。
        continue
    _raw = os.getenv(_key)
    if _raw is None:
        continue
    _CONFIG[_key] = _coerce_by_default_type(_raw, _default)

# 规则驱动后处理：按维护区中的 _POST_NORMALIZE_RULES 执行。
for _key, _rule in _POST_NORMALIZE_RULES.items():
    _kind = _rule.get("kind")
    _fallback = _DEFAULT_CONFIG.get(_key, _rule.get("fallback"))
    _value = _CONFIG.get(_key)
    if _kind == "str_dict":
        _CONFIG[_key] = _normalize_str_dict(_value, _fallback)
    elif _kind == "int_dict":
        _CONFIG[_key] = _normalize_int_dict(_value, _fallback)

# 规则驱动扩展：按维护区中的 _EXTRA_ENV_RULES 执行。
for _key, _rule in _EXTRA_ENV_RULES.items():
    _raw = os.getenv(_key)
    if _raw is None:
        continue
    _parser = _rule.get("parser")
    if _parser == "float":
        try:
            _CONFIG[_key] = float(_raw)
        except ValueError:
            continue

# docker-limited 分支硬切换：忽略环境里的 IMPORT_RULES，统一锁定受限白名单。
_CONFIG["IMPORT_RULES"] = dict(_LOCKED_IMPORT_RULES)

# 导出配置常量
for _key, _value in _CONFIG.items():
    if _EXPORT_UPPERCASE_ONLY:
        if not _key.isupper():
            continue
        globals()[_key] = _value
        continue
    globals()[_key] = _value

print(__file__)
