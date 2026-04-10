from __future__ import annotations

import os

import tushare as ts

TOKEN = os.getenv("TUSHARE_CLIENT_TOKEN", "test")
BASE_URL = os.getenv("TUSHARE_GATEWAY_HTTP_URL", "https://dev.tushare.000666.site/dataapi")

pro = ts.pro_api(TOKEN)
pro._DataApi__http_url = BASE_URL.rstrip("/")

df = pro.index_basic(
    **{"limit": 5},
    fields=["ts_code", "name", "market", "publisher", "category", "base_date"],
)

print(df)
