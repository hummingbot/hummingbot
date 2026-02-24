import asyncio
import time
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.derivative.grvt_perpetual.grvt_api_order_book_data_source import (
    GrvtAPIOrderBookDataSource,
)
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class GrvtAPIOrderBookDataSourceTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.connector = MagicMock()
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC-USDC")
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="BTC-USDC")
        self.api_factory = MagicMock()
        self.rest = AsyncMock()
        self.api_factory.get_rest_assistant = AsyncMock(return_value=self.rest)
        self.data_source = GrvtAPIOrderBookDataSource(
            trading_pairs=["BTC-USDC"],
            connector=self.connector,
            api_factory=self.api_factory,
        )

    def test_order_book_snapshot_parsing(self):
        self.rest.execute_request = AsyncMock(
            return_value={
                "data": {
                    "symbol": "BTC-USDC",
                    "timestamp": int(time.time() * 1000),
                    "bids": [["50000", "1"]],
                    "asks": [["50010", "2"]],
                }
            }
        )
        msg = asyncio.get_event_loop().run_until_complete(self.data_source._order_book_snapshot("BTC-USDC"))
        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual("BTC-USDC", msg.content["trading_pair"])
        self.assertEqual(1, len(msg.content["bids"]))
        self.assertEqual(1, len(msg.content["asks"]))

    def test_channel_originating_message(self):
        self.assertEqual(
            self.data_source._trade_messages_queue_key,
            self.data_source._channel_originating_message({"channel": "trades:BTC-USDC"}),
        )
        self.assertEqual(
            self.data_source._funding_info_messages_queue_key,
            self.data_source._channel_originating_message({"channel": "funding:BTC-USDC"}),
        )
