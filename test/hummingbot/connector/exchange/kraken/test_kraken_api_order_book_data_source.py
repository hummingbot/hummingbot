import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Awaitable, Dict, List
from unittest.mock import patch, AsyncMock

from aioresponses import aioresponses

from hummingbot.connector.exchange.kraken.kraken_api_order_book_data_source import KrakenAPIOrderBookDataSource
from hummingbot.connector.exchange.kraken import kraken_constants as CONSTANTS
from hummingbot.connector.exchange.kraken.kraken_constants import KrakenAPITier
from hummingbot.connector.exchange.kraken.kraken_utils import build_rate_limits_by_tier
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook, OrderBookMessage
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class KrakenAPIOrderBookDataSourceTest(unittest.TestCase):
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
        self.data_source = KrakenAPIOrderBookDataSource(self.throttler, trading_pairs=[self.trading_pair])

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_last_traded_prices_mock(self, last_trade_close: Decimal) -> Dict:
        last_traded_prices = {
            "error": [],
            "result": {
                f"X{self.base_asset}{self.quote_asset}": {
                    "a": [
                        "52609.60000",
                        "1",
                        "1.000"
                    ],
                    "b": [
                        "52609.50000",
                        "1",
                        "1.000"
                    ],
                    "c": [
                        str(last_trade_close),
                        "0.00080000"
                    ],
                    "v": [
                        "1920.83610601",
                        "7954.00219674"
                    ],
                    "p": [
                        "52389.94668",
                        "54022.90683"
                    ],
                    "t": [
                        23329,
                        80463
                    ],
                    "l": [
                        "51513.90000",
                        "51513.90000"
                    ],
                    "h": [
                        "53219.90000",
                        "57200.00000"
                    ],
                    "o": "52280.40000"
                }
            }
        }
        return last_traded_prices

    def get_depth_mock(self) -> Dict:
        depth = {
            "error": [],
            "result": {
                f"X{self.base_asset}{self.quote_asset}": {
                    "asks": [
                        [
                            "52523.00000",
                            "1.199",
                            1616663113
                        ],
                        [
                            "52536.00000",
                            "0.300",
                            1616663112
                        ]
                    ],
                    "bids": [
                        [
                            "52522.90000",
                            "0.753",
                            1616663112
                        ],
                        [
                            "52522.80000",
                            "0.006",
                            1616663109
                        ]
                    ]
                }
            }
        }
        return depth

    def get_public_asset_pair_mock(self) -> Dict:
        asset_pairs = {
            "error": [],
            "result": {
                f"X{self.base_asset}{self.quote_asset}": {
                    "altname": f"{self.base_asset}{self.quote_asset}",
                    "wsname": f"{self.base_asset}/{self.quote_asset}",
                    "aclass_base": "currency",
                    "base": self.base_asset,
                    "aclass_quote": "currency",
                    "quote": self.quote_asset,
                    "lot": "unit",
                    "pair_decimals": 5,
                    "lot_decimals": 8,
                    "lot_multiplier": 1,
                    "leverage_buy": [
                        2,
                        3,
                        4,
                        5
                    ],
                    "leverage_sell": [
                        2,
                        3,
                        4,
                        5
                    ],
                    "fees": [
                        [
                            0,
                            0.26
                        ],
                        [
                            50000,
                            0.24
                        ],
                    ],
                    "fees_maker": [
                        [
                            0,
                            0.16
                        ],
                        [
                            50000,
                            0.14
                        ],
                    ],
                    "fee_volume_currency": "ZUSD",
                    "margin_call": 80,
                    "margin_stop": 40,
                    "ordermin": "0.005"
                },
            }
        }
        return asset_pairs

    def get_trade_data_mock(self) -> List:
        trade_data = [
            0,
            [
                [
                    "5541.20000",
                    "0.15850568",
                    "1534614057.321597",
                    "s",
                    "l",
                    ""
                ],
                [
                    "6060.00000",
                    "0.02455000",
                    "1534614057.324998",
                    "b",
                    "l",
                    ""
                ]
            ],
            "trade",
            f"{self.base_asset}/{self.quote_asset}"
        ]
        return trade_data

    @aioresponses()
    def test_get_last_traded_prices(self, mocked_api):
        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.TICKER_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        last_traded_price = Decimal("52641.10000")
        resp = self.get_last_traded_prices_mock(last_trade_close=last_traded_price)
        mocked_api.get(regex_url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(
            KrakenAPIOrderBookDataSource.get_last_traded_prices(
                trading_pairs=[self.trading_pair], throttler=self.throttler
            )
        )

        self.assertIn(self.trading_pair, ret)
        self.assertEqual(float(last_traded_price), ret[self.trading_pair])

    @aioresponses()
    def test_get_new_order_book(self, mocked_api):
        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.SNAPSHOT_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_depth_mock()
        mocked_api.get(regex_url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

        self.assertTrue(isinstance(ret, OrderBook))

        bids_df, asks_df = ret.snapshot
        pair_data = resp["result"][f"X{self.base_asset}{self.quote_asset}"]
        first_bid_price = float(pair_data["bids"][0][0])
        first_ask_price = float(pair_data["asks"][0][0])

        self.assertEqual(first_bid_price, bids_df.iloc[0]["price"])
        self.assertEqual(first_ask_price, asks_df.iloc[0]["price"])

    @aioresponses()
    def test_fetch_trading_pairs(self, mocked_api):
        url = f"{CONSTANTS.BASE_URL}{CONSTANTS.ASSET_PAIRS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_public_asset_pair_mock()
        mocked_api.get(regex_url, body=json.dumps(resp))

        resp = self.async_run_with_timeout(KrakenAPIOrderBookDataSource.fetch_trading_pairs())

        self.assertTrue(len(resp) == 1)
        self.assertIn(self.trading_pair, resp)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_trades(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = self.get_trade_data_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(resp)
        )
        output_queue = asyncio.Queue()

        self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, output_queue))
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(websocket_mock=ws_connect_mock.return_value)

        self.assertTrue(not output_queue.empty())
        msg = output_queue.get_nowait()
        self.assertTrue(isinstance(msg, OrderBookMessage))
        first_trade_price = resp[1][0][0]
        self.assertEqual(msg.content["price"], first_trade_price)

        self.assertTrue(not output_queue.empty())
        msg = output_queue.get_nowait()
        self.assertTrue(isinstance(msg, OrderBookMessage))
        second_trade_price = resp[1][1][0]
        self.assertEqual(msg.content["price"], second_trade_price)
