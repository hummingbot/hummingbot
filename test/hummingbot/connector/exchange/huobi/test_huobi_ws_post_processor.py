import asyncio
import gzip
import json
import unittest

from typing import Any, Awaitable, Dict

from hummingbot.connector.exchange.huobi.huobi_ws_post_processor import HuobiWSPostProcessor
from hummingbot.core.web_assistant.connections.data_types import WSResponse


class HuobiWSPostProcessorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}".lower()

    def setUp(self) -> None:
        super().setUp()

        self.post_processor = HuobiWSPostProcessor()

    def _compress(self, message: Dict[str, Any]) -> bytes:
        return gzip.compress(json.dumps(message).encode())

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_post_process(self):

        # Only Market data is compressed by GZIP
        orderbook_message: bytes = self._compress(
            message={
                "ch": f"market.{self.ex_trading_pair}.depth.step0",
                "ts": 1630983549503,
                "tick": {
                    "bids": [[52690.69, 0.36281], [52690.68, 0.2]],
                    "asks": [[52690.7, 0.372591], [52691.26, 0.13]],
                    "version": 136998124622,
                    "ts": 1630983549500,
                },
            }
        )

        orderbook_response: WSResponse = WSResponse(data=orderbook_message)

        result_response: WSResponse = self.async_run_with_timeout(self.post_processor.post_process(orderbook_response))

        self.assertIsInstance(result_response.data, Dict)
        self.assertIn(self.ex_trading_pair, str(result_response.data))

        # User stream message is NOT compressed by GZIP
        account_message = {
            "action": "push",
            "ch": "accounts.update#2",
            "data": {
                "currency": self.quote_asset,
                "accountId": 15026496,
                "balance": "100.0",
                "available": "10.0",
                "changeType": None,
                "accountType": "trade",
                "changeTime": None,
                "seqNum": 804,
            },
        }

        account_response: WSResponse = WSResponse(data=account_message)

        result_response: WSResponse = self.async_run_with_timeout(self.post_processor.post_process(account_response))

        self.assertIsInstance(result_response.data, Dict)
        self.assertIn(self.quote_asset, str(result_response.data))
        self.assertEqual("100.0", result_response.data["data"]["balance"])
        self.assertEqual("10.0", result_response.data["data"]["available"])
