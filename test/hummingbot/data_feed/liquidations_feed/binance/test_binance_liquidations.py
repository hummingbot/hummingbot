import asyncio
import json
import unittest
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.liquidations_feed.binance import BinancePerpetualLiquidations, constants as CONSTANTS
from hummingbot.data_feed.liquidations_feed.liquidations_base import LiquidationSide


class TestBinanceLiquidations(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.liquidations_feed = BinancePerpetualLiquidations(trading_pairs=set(), max_retention_seconds=15)

        self.log_records = []

        self.liquidations_feed.logger().setLevel(1)
        self.liquidations_feed.logger().addHandler(self)
        self.liquidations_feed._trading_pairs_map = self.get_trading_pairs_map()

        self.resume_test_event = asyncio.Event()

    def handle(self, record):
        self.log_records.append(record)

    def is_logged(self, log_level: str, message: str) -> bool:
        return any(
            record.levelname == log_level and record.getMessage() == message for
            record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_liquidations_ws_data_mock_1(self):
        data = {"e": "forceOrder",
                "E": 1714242617159,
                "o": {"s": "GLMUSDT",
                      "S": "BUY",
                      "o": "LIMIT",
                      "f": "IOC",
                      "q": "9970",
                      "p": "0.5088718",
                      "ap": "0.5029243",
                      "X": "FILLED",
                      "l": "988",
                      "z": "9970",
                      "T": 1714242617155
                      }
                }
        return data

    def get_liquidations_ws_data_mock_2(self):
        data = {"e": "forceOrder",
                "E": 1714242964102,
                "o": {"s": "CTSIUSDT",
                      "S": "SELL",
                      "o": "LIMIT",
                      "f": "IOC",
                      "q": "975",
                      "p": "0.2240",
                      "ap": "0.2197",
                      "X": "FILLED",
                      "l": "975",
                      "z": "975",
                      "T": 1714242964100
                      }
                }
        return data

    def get_trading_pairs_map(self) -> bidict:
        trading_pairs_map = bidict()
        trading_pairs_map["CTSIUSDT"] = "CTSI-USDT"
        trading_pairs_map["GLMUSDT"] = "GLM-USDT"
        return trading_pairs_map

    def get_exchange_info(self):
        data = {
            "timezone": "UTC",
            "serverTime": 1714240806674,
            "futuresType": "U_MARGINED",
            "rateLimits": [
                {
                    "rateLimitType": "REQUEST_WEIGHT",
                    "interval": "MINUTE",
                    "intervalNum": 1,
                    "limit": 2400
                },
                {
                    "rateLimitType": "ORDERS",
                    "interval": "MINUTE",
                    "intervalNum": 1,
                    "limit": 1200
                },
                {
                    "rateLimitType": "ORDERS",
                    "interval": "SECOND",
                    "intervalNum": 10,
                    "limit": 300
                }
            ],
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "pair": "BTCUSDT",
                    "contractType": "PERPETUAL",
                    "deliveryDate": 4133404800000,
                    "onboardDate": 1569398400000,
                    "status": "TRADING",
                    "maintMarginPercent": "2.5000",
                    "requiredMarginPercent": "5.0000",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "marginAsset": "USDT",
                    "pricePrecision": 2,
                    "quantityPrecision": 3,
                    "baseAssetPrecision": 8,
                    "quotePrecision": 8,
                    "underlyingType": "COIN",
                    "underlyingSubType": [
                        "PoW"
                    ],
                    "settlePlan": 0,
                    "triggerProtect": "0.0500",
                    "liquidationFee": "0.012500",
                    "marketTakeBound": "0.05",
                    "maxMoveOrderLimit": 10000
                },
                {
                    "symbol": "ETHUSDT",
                    "pair": "ETHUSDT",
                    "contractType": "PERPETUAL",
                    "deliveryDate": 4133404800000,
                    "onboardDate": 1569398400000,
                    "status": "TRADING",
                    "maintMarginPercent": "2.5000",
                    "requiredMarginPercent": "5.0000",
                    "baseAsset": "ETH",
                    "quoteAsset": "USDT",
                    "marginAsset": "USDT",
                    "pricePrecision": 2,
                    "quantityPrecision": 3,
                    "baseAssetPrecision": 8,
                    "quotePrecision": 8,
                    "underlyingType": "COIN",
                    "underlyingSubType": [
                        "Layer-1"
                    ],
                    "settlePlan": 0,
                    "triggerProtect": "0.0500",
                    "liquidationFee": "0.012500",
                    "marketTakeBound": "0.05",
                    "maxMoveOrderLimit": 10000,
                }
            ]
        }
        return data

    def test_liquidations_empty(self):
        self.assertTrue(self.liquidations_feed.liquidations_df().empty)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_all_liquidations(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_liquidations = {
            "result": None,
            "id": 1
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_liquidations))

        self.listening_task = self.ev_loop.create_task(self.liquidations_feed.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(1, len(sent_subscription_messages))
        expected_liquidations_subscription = {
            "method": "SUBSCRIBE",
            "params": ["!forceOrder@arr"],
            "id": 1}

        self.assertEqual(expected_liquidations_subscription, sent_subscription_messages[0])

        self.assertTrue(self.is_logged(
            "INFO",
            "Subscribed to public liquidations..."
        ))

    @patch("hummingbot.data_feed.liquidations_feed.binance.BinancePerpetualLiquidations._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _: AsyncMock):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.liquidations_feed.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

    @patch("hummingbot.data_feed.liquidations_feed.binance.BinancePerpetualLiquidations._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock: AsyncMock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(
            asyncio.CancelledError())

        self.listening_task = self.ev_loop.create_task(self.liquidations_feed.listen_for_subscriptions())

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self.is_logged(
                "ERROR",
                "Unexpected error occurred when listening to public liquidations. Retrying in 1 seconds..."))

    def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.liquidations_feed._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

    def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            self.listening_task = self.ev_loop.create_task(self.liquidations_feed._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

        self.assertTrue(
            self.is_logged("ERROR", "Unexpected error occurred subscribing to public liquidations...")
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_process_websocket_messages_with_two_valid_messages(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self.get_liquidations_ws_data_mock_1()))

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self.get_liquidations_ws_data_mock_2()))

        self.listening_task = self.ev_loop.create_task(self.liquidations_feed.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        all_liquidations_df = self.liquidations_feed.liquidations_df()
        ctsi_liquidations_df = self.liquidations_feed.liquidations_df("CTSI-USDT")

        self.assertEqual(len(all_liquidations_df), 2)
        self.assertEqual(len(ctsi_liquidations_df), 1)
        self.assertEqual(ctsi_liquidations_df["trading_pair"][0], "CTSI-USDT")
        self.assertEqual(ctsi_liquidations_df["quantity"][0], 975.0)
        self.assertEqual(ctsi_liquidations_df["side"][0], LiquidationSide.LONG)

        # test the time based cleanup which should clear all liquidations since they are in the past
        self.liquidations_feed._cleanup_old_liquidations()
        all_liquidations_df = self.liquidations_feed.liquidations_df()
        self.assertEqual(len(all_liquidations_df), 0)

    @aioresponses()
    def test_get_exchange_info(self, mock_api: aioresponses):
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.EXCHANGE_INFO}"

        mock_api.get(url=url, body=json.dumps(self.get_exchange_info()))

        self.async_run_with_timeout(self.liquidations_feed._fetch_and_map_trading_pairs())

        self.assertIn("BTCUSDT", self.liquidations_feed._trading_pairs_map)
        self.assertIn("ETHUSDT", self.liquidations_feed._trading_pairs_map)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception
