from __future__ import annotations

import unittest
from unittest.mock import patch

from ksrpc.server import tushare_gateway


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload
        self.ok = True
        self.status_code = 200
        self.content = b'{"code":40204,"msg":"ip blocked"}'
        self.text = self.content.decode("utf-8")

    def json(self) -> dict[str, object]:
        return self._payload


class TushareGatewayTest(unittest.TestCase):
    def test_query_returns_structured_upstream_business_error(self) -> None:
        payload = {"code": 40204, "msg": "您的IP数量超限，最大数量为2个！", "data": None}
        with patch.dict("os.environ", {"TUSHARE_TOKEN": "test-token"}, clear=False):
            with patch("ksrpc.server.tushare_gateway.requests.post", return_value=_FakeResponse(payload)):
                with patch("ksrpc.server.tushare_gateway.add_upstream_bytes", return_value=321):
                    result = tushare_gateway.query(client_token="test", api_name="index_basic")

        self.assertEqual(
            result,
            {
                "upstream_error": {"code": 40204, "msg": "您的IP数量超限，最大数量为2个！"},
                "upstream_bytes": len(b'{"code":40204,"msg":"ip blocked"}'),
                "quota_bytes_used_after": 321,
            },
        )


if __name__ == "__main__":
    unittest.main()
