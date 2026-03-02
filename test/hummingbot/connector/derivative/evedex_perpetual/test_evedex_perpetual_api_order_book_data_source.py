import asyncio
import json
import re
from typing import Awaitable, Dict, List, Optional
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_api_order_book_data_source import (
    EvedexPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class EvedexPerpetualAPIOrderBookDataSourceTests(TestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"
        cls.domain = "evedex_perpetual"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()
        
        self.connector = MagicMock()
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.trading_pair)
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)
        self.connector._api_get = AsyncMock()
        self.connector.get_last_traded_prices = AsyncMock(return_value={self.trading_pair: 50000.0})
        
        self.api_factory = MagicMock()
        
        self.data_source = EvedexPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.api_factory,
            domain=self.domain
        )
        
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_get_last_traded_prices(self):
        """Test getting last traded prices."""
        result = self.async_run_with_timeout(
            self.data_source.get_last_traded_prices([self.trading_pair])
        )
        
        self.assertEqual(result[self.trading_pair], 50000.0)
        self.connector.get_last_traded_prices.assert_called_once_with(trading_pairs=[self.trading_pair])

    def test_request_order_book_snapshot(self):
        """Test order book snapshot request."""
        mock_response = {
            "data": {
                "timestamp": 1234567890000,
                "bids": [["50000", "1.5"], ["49900", "2.0"]],
                "asks": [["50100", "1.0"], ["50200", "1.2"]]
            }
        }
        self.connector._api_get.return_value = mock_response
        
        result = self.async_run_with_timeout(
            self.data_source._request_order_book_snapshot(self.trading_pair)
        )
        
        self.assertEqual(result["data"]["timestamp"], 1234567890000)
        self.assertEqual(len(result["data"]["bids"]), 2)
        self.assertEqual(len(result["data"]["asks"]), 2)

    def test_order_book_snapshot(self):
        """Test order book snapshot message creation."""
        mock_response = {
            "data": {
                "timestamp": 1234567890000,
                "bids": [["50000", "1.5"], ["49900", "2.0"]],
                "asks": [["50100", "1.0"], ["50200", "1.2"]]
            }
        }
        self.connector._api_get.return_value = mock_response
        
        result = self.async_run_with_timeout(
            self.data_source._order_book_snapshot(self.trading_pair)
        )
        
        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(result.type, OrderBookMessageType.SNAPSHOT)
        self.assertEqual(result.trading_pair, self.trading_pair)
        self.assertEqual(len(result.bids), 2)
        self.assertEqual(len(result.asks), 2)

    def test_get_funding_info(self):
        """Test getting funding info."""
        mock_response = {
            "data": {
                "indexPrice": "50000",
                "markPrice": "50050",
                "fundingRate": "0.0001"
            }
        }
        self.connector._api_get.return_value = mock_response
        
        result = self.async_run_with_timeout(
            self.data_source.get_funding_info(self.trading_pair)
        )
        
        self.assertEqual(float(result.index_price), 50000)
        self.assertEqual(float(result.mark_price), 50050)
        self.assertEqual(float(result.rate), 0.0001)

    def test_next_funding_time(self):
        """Test next funding time calculation."""
        next_time = self.data_source._next_funding_time()
        
        # Should be a future timestamp
        import time
        self.assertGreater(next_time, time.time())
        
        # Should be aligned to 8-hour intervals
        self.assertEqual(next_time % 28800, 0)

    def test_channel_originating_message_orderbook(self):
        """Test channel identification for orderbook messages."""
        message = {
            "push": {
                "channel": f"{CONSTANTS.WS_ORDERBOOK_CHANNEL}:BTCUSDT"
            }
        }
        
        channel = self.data_source._channel_originating_message(message)
        self.assertEqual(channel, self.data_source._snapshot_messages_queue_key)

    def test_channel_originating_message_trades(self):
        """Test channel identification for trade messages."""
        message = {
            "push": {
                "channel": f"{CONSTANTS.WS_TRADES_CHANNEL}:BTCUSDT"
            }
        }
        
        channel = self.data_source._channel_originating_message(message)
        self.assertEqual(channel, self.data_source._trade_messages_queue_key)

    def test_channel_originating_message_unknown(self):
        """Test channel identification for unknown messages."""
        message = {
            "push": {
                "channel": "unknown:channel"
            }
        }
        
        channel = self.data_source._channel_originating_message(message)
        self.assertEqual(channel, "")
