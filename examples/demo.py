"""
仅技术交流演示，请购买数据授权。
"""

import atexit
import os
os.environ["PRINT"] = "0"

import nest_asyncio
import tushare as ts
from ksrpc.client import RpcClient
from ksrpc.connections.http import HttpConnection
from ksrpc.hack.tushare import hack
from ksrpc.utils.async_ import async_to_sync


# --------------------------
# 固定初始化代码（pip install ksrpc==0.7.0）
# demo更新地址: https://github.com/quantman888/ksrpc/blob/docker-stable/examples/demo.py
# --------------------------
nest_asyncio.apply()

_CONN = None


def _enable_ksrpc_proxy() -> None:
    global _CONN

    url = os.getenv("KSRPC_URL", "https://your.domain/api/v1/{time}")
    username = os.getenv("KSRPC_USERNAME", "test")
    password = os.getenv("KSRPC_PASSWORD", "123")

    _CONN = HttpConnection(url, username, password)
    client = RpcClient("ksrpc.server.tushare", _CONN, to_sync=True)
    hack(client)


@atexit.register
def _cleanup_conn() -> None:
    global _CONN
    if _CONN is None:
        return
    try:
        async_to_sync(_CONN.reset)
    except Exception:
        pass
    _CONN = None


_enable_ksrpc_proxy()
# --------------------------


# ----------------------
# 用户业务代码（tushare 风格）
# ----------------------
pro = ts.pro_api(token=os.getenv("TUSHARE_TOKEN"), timeout=30)
df = pro.daily(ts_code="000001.SZ", start_date="20180701", end_date="20180718")

print(df)
