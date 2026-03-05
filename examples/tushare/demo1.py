import nest_asyncio

from ksrpc.client import RpcClient
from ksrpc.connections.websocket import WebSocketConnection

pro = ts.pro_api(token=os.getenv("TUSHARE_TOKEN", ""), timeout=30)

# 必用，否则同步模式只能调用第一次，第二次会报 RuntimeError: Event loop is closed
nest_asyncio.apply()

conn = WebSocketConnection(URL_WS, USERNAME, PASSWORD)
pro = RpcClient("ksrpc.server.tushare", conn, to_sync=True)

df = pro.daily(ts_code="000001.SZ", start_date="20180701", end_date="20180718")

print(df)
del conn
