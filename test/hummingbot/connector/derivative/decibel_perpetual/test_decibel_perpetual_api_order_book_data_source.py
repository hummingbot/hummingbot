import asyncio
import json
import time
import unittest
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from hummingbot.connector.derivative.decibel_perpetual import decibel_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_api_order_book_data_source import (
    DecibelPerpetualAPIOrderBookDataSource,
)
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class TestDecibelPerpetualAPIOrderBookDataSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.get_event_loop()

    def setUp(self):
        self.trading_pairs = ["BTC-USD"]
        self.connector = MagicMock()
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC-PERP")
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="BTC-USD")
        self.connector.market_name_to_address = {"BTC-PERP": "0xmarket_btc_address"}
        self.connector._auth = MagicMock()
        self.connector._auth.get_ws_protocols.return_value = ["decibel", "test_key"]

        self.api_factory = MagicMock()
        self.data_source = DecibelPerpetualAPIOrderBookDataSource(
            trading_pairs=self.trading_pairs,
            connector=self.connector,
            api_factory=self.api_factory,
            domain=CONSTANTS.DOMAIN,
        )

    def _mock_prices_response(self) -> List[Dict[str, Any]]:
        return [
            {
                "market": "0xmarket_btc_address",
                "symbol": "BTC-PERP",
                "oracle_price": "97250.50",
                "mark_price": "97248.30",
                "mid_price": "97249.00",
                "funding_rate": "0.0001",
            }
        ]

    def _mock_depth_response(self) -> Dict[str, Any]:
        return {
            "bids": [
                {"price": "97240.00", "size": "1.5"},
                {"price": "97235.00", "size": "2.0"},
            ],
            "asks": [
                {"price": "97260.00", "size": "1.2"},
                {"price": "97265.00", "size": "0.8"},
            ],
        }

    def test_get_funding_info(self):
        self.connector._api_get = AsyncMock(return_value=self._mock_prices_response())
        funding_info = self.ev_loop.run_until_complete(
            self.data_source.get_funding_info("BTC-USD")
        )
        self.assertIsInstance(funding_info, FundingInfo)
        self.assertEqual(funding_info.trading_pair, "BTC-USD")
        self.assertEqual(funding_info.index_price, Decimal("97250.50"))
        self.assertEqual(funding_info.mark_price, Decimal("97248.30"))
        self.assertEqual(funding_info.rate, Decimal("0.0001"))

    def test_get_funding_info_not_found(self):
        self.connector._api_get = AsyncMock(return_value=[])
        funding_info = self.ev_loop.run_until_complete(
            self.data_source.get_funding_info("BTC-USD")
        )
        self.assertEqual(funding_info.index_price, Decimal("0"))
        self.assertEqual(funding_info.mark_price, Decimal("0"))

    def test_request_order_book_snapshot(self):
        self.connector._api_get = AsyncMock(return_value=self._mock_depth_response())
        snapshot = self.ev_loop.run_until_complete(
            self.data_source._request_order_book_snapshot("BTC-USD")
        )
        self.assertIn("bids", snapshot)
        self.assertIn("asks", snapshot)
        self.assertEqual(len(snapshot["bids"]), 2)
        self.assertEqual(len(snapshot["asks"]), 2)

    def test_order_book_snapshot_message(self):
        self.connector._api_get = AsyncMock(return_value=self._mock_depth_response())
        snapshot_msg = self.ev_loop.run_until_complete(
            self.data_source._order_book_snapshot("BTC-USD")
        )
        self.assertIsInstance(snapshot_msg, OrderBookMessage)
        self.assertEqual(snapshot_msg.type, OrderBookMessageType.SNAPSHOT)

    def test_channel_originating_message_depth(self):
        msg = {"topic": "depth:0xmarket_btc_address", "data": {}}
        channel = self.data_source._channel_originating_message(msg)
        self.assertEqual(channel, "order_book_snapshot")

    def test_channel_originating_message_trades(self):
        msg = {"topic": "trades:0xmarket_btc_address", "data": []}
        channel = self.data_source._channel_originating_message(msg)
        self.assertEqual(channel, self.data_source._trade_messages_queue_key)

    def test_channel_originating_message_prices(self):
        msg = {"topic": "prices:0xmarket_btc_address", "data": {}}
        channel = self.data_source._channel_originating_message(msg)
        self.assertEqual(channel, "funding_info")

    def test_channel_originating_message_unknown(self):
        msg = {"result": "ok"}
        channel = self.data_source._channel_originating_message(msg)
        self.assertEqual(channel, "")

    def test_parse_trade_message(self):
        raw_message = {
            "topic": "trades:0xmarket_btc_address",
            "data": [
                {
                    "trade_id": "trade_001",
                    "price": "97250.00",
                    "size": "0.5",
                    "side": "buy",
                    "timestamp": time.time(),
                }
            ],
        }
        self.connector.market_name_to_address = {"BTC-PERP": "0xmarket_btc_address"}
        queue = asyncio.Queue()
        self.ev_loop.run_until_complete(
            self.data_source._parse_trade_message(raw_message, queue)
        )
        self.assertFalse(queue.empty())
        msg = queue.get_nowait()
        self.assertIsInstance(msg, OrderBookMessage)
        self.assertEqual(msg.type, OrderBookMessageType.TRADE)

    def test_next_funding_time(self):
        funding_time = self.data_source._next_funding_time()
        self.assertGreater(funding_time, time.time())
        # Should be within the next hour
        self.assertLessEqual(funding_time - time.time(), 3600)


if __name__ == "__main__":
    unittest.main()
