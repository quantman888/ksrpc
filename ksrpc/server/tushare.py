"""
TuShare服务转发
1. 屏蔽set_token功能，由服务端进行统一认证
2. 客户端替换了pro, 服务端将请求转到pro

"""
import os
import threading

import tushare as ts

_TOKEN = os.getenv("TUSHARE_TOKEN", "")
_TIMEOUT = 30
_LOCAL = threading.local()

__path__ = []
__all__ = []


def _get_pro():
    # 每个工作线程维护独立的 Tushare client，避免并发下共享 client 争用
    if not hasattr(_LOCAL, "pro"):
        _LOCAL.pro = ts.pro_api(token=_TOKEN, timeout=_TIMEOUT)
    return _LOCAL.pro


def __getattr__(name):
    attr = getattr(_get_pro(), name)
    if not callable(attr):
        return attr

    def _dispatch(*args, **kwargs):
        return getattr(_get_pro(), name)(*args, **kwargs)

    return _dispatch


def set_token(token):
    # 防止用户调用到了pro.set_token
    pass


def get_token():
    return ""


def pro_api(token='', timeout=30):
    # 防止用户调用到了pro.pro_api
    pass
