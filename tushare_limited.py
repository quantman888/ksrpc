"""受限转发模块：仅开放 opt_mins。"""
from importlib import import_module


__all__ = ["opt_mins"]


def opt_mins(*args, **kwargs):
    return import_module("ksrpc.server.tushare").opt_mins(*args, **kwargs)
