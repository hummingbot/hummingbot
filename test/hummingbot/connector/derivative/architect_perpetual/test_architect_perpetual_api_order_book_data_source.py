import asyncio
from decimal import Decimal
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_api_order_book_data_source import (
    ArchitectPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class ArchitectPerpetualAPIOrderBookDataSourceTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.trading_pairs = ["BTC-USD", "ETH-USD"]

        self.connector = MagicMock()
        self.connector.exchange_symbol_to_trading_pair = MagicMock(
            side_effect=lambda x: x.replace("-PERP", "").replace("_", "-")
        )
        self.connector.trading_pair_to_exchange_symbol = MagicMock(
            side_effect=lambda x: f"{x}-PERP"
        )

        self.api_factory = MagicMock()

        self.data_source = ArchitectPerpetualAPIOrderBookDataSource(
            trading_pairs=self.trading_pairs,
            connector=self.connector,
            api_factory=self.api_factory,
            domain=CONSTANTS.DOMAIN,
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_init(self):
        self.assertEqual(self.data_source._trading_pairs, self.trading_pairs)
        self.assertEqual(self.data_source._domain, CONSTANTS.DOMAIN)

    @patch("hummingbot.connector.derivative.architect_perpetual.architect_perpetual_api_order_book_data_source.ArchitectPerpetualAPIOrderBookDataSource._api_factory")
    async def test_get_last_traded_prices(self):
        mock_response = [
            {"symbol": "BTC-USD-PERP", "last_price": "42000.50"},
            {"symbol": "ETH-USD-PERP", "last_price": "2200.25"},
        ]

        mock_rest_assistant = AsyncMock()
        mock_rest_assistant.execute_request = AsyncMock(return_value=mock_response)
        self.api_factory.get_rest_assistant = AsyncMock(return_value=mock_rest_assistant)

        result = await self.data_source.get_last_traded_prices(self.trading_pairs)

        self.assertIn("BTC-USD", result)
        self.assertIn("ETH-USD", result)

    def test_process_order_book_message_creates_diff(self):
        data = {
            "type": "orderbook",
            "symbol": "BTC-USD-PERP",
            "sequence": 12345,
            "bids": [["42000", "1.5"]],
            "asks": [["42001", "2.0"]],
        }

        self.data_source._message_queue["BTC-USD"] = asyncio.Queue()

        self.async_run_with_timeout(self.data_source._process_order_book_message(data))

        self.assertFalse(self.data_source._message_queue["BTC-USD"].empty())

    def test_process_trade_message_creates_trade(self):
        data = {
            "type": "trade",
            "symbol": "BTC-USD-PERP",
            "trade_id": "trade123",
            "side": "buy",
            "price": "42000.5",
            "size": "0.1",
        }

        self.data_source._message_queue["BTC-USD"] = asyncio.Queue()

        self.async_run_with_timeout(self.data_source._process_trade_message(data))

        self.assertFalse(self.data_source._message_queue["BTC-USD"].empty())
