import asyncio
import json
import re
import unittest
from typing import Awaitable, Dict, List
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses

from hummingbot.connector.exchange.kraken.kraken_api_user_stream_data_source import KrakenAPIUserStreamDataSource
from hummingbot.connector.exchange.kraken.kraken_auth import KrakenAuth
from hummingbot.connector.exchange.kraken import kraken_constants as CONSTANTS
from hummingbot.connector.exchange.kraken.kraken_constants import KrakenAPITier
from hummingbot.connector.exchange.kraken.kraken_utils import build_rate_limits_by_tier
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class KrakenAPIUserStreamDataSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.api_tier = KrakenAPITier.STARTER

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.throttler = AsyncThrottler(build_rate_limits_by_tier(self.api_tier))
        not_a_real_secret = "kQH5HW/8p1uGOVjbgWA7FunAmGO8lsSUXNsu3eow76sz84Q18fWxnyRzBHCd3pd5nE9qa99HAZtuZuj6F1huXg=="
        kraken_auth = KrakenAuth(api_key="someKey", secret_key=not_a_real_secret)
        self.data_source = KrakenAPIUserStreamDataSource(self.throttler, kraken_auth)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @staticmethod
    def get_auth_response_mock() -> Dict:
        auth_resp = {
            "error": [],
            "result": {
                "token": "1Dwc4lzSwNWOAwkMdqhssNNFhs1ed606d1WcF3XfEMw",
                "expires": 900
            }
        }
        return auth_resp

    @staticmethod
    def get_open_orders_mock() -> List:
        open_orders = [
            [
                {
                    "OGTT3Y-C6I3P-XRI6HX": {
                        "status": "closed"
                    }
                },
                {
                    "OGTT3Y-C6I3P-XRI6HX": {
                        "status": "closed"
                    }
                }
            ],
            "openOrders",
            {
                "sequence": 59342
            }
        ]
        return open_orders

    @staticmethod
    def get_own_trades_mock() -> List:
        own_trades = [
            [
                {
                    "TDLH43-DVQXD-2KHVYY": {
                        "cost": "1000000.00000",
                        "fee": "1600.00000",
                        "margin": "0.00000",
                        "ordertxid": "TDLH43-DVQXD-2KHVYY",
                        "ordertype": "limit",
                        "pair": "XBT/EUR",
                        "postxid": "OGTT3Y-C6I3P-XRI6HX",
                        "price": "100000.00000",
                        "time": "1560516023.070651",
                        "type": "sell",
                        "vol": "1000000000.00000000"
                    }
                },
            ],
            "ownTrades",
            {
                "sequence": 2948
            }
        ]
        return own_trades

    @aioresponses()
    def test_get_auth_token(self, mocked_api):
        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.GET_TOKEN_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_auth_response_mock()
        mocked_api.post(regex_url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(self.data_source.get_auth_token())

        self.assertEqual(ret, resp["result"]["token"])

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream(self, mocked_api, ws_connect_mock):
        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.GET_TOKEN_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_auth_response_mock()
        mocked_api.post(regex_url, body=json.dumps(resp))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        output_queue = asyncio.Queue()
        self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, output_queue))

        resp = self.get_open_orders_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(resp)
        )
        ret = self.async_run_with_timeout(coroutine=output_queue.get())

        self.assertEqual(ret, resp)

        resp = self.get_own_trades_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(resp)
        )
        ret = self.async_run_with_timeout(coroutine=output_queue.get())

        self.assertEqual(ret, resp)
