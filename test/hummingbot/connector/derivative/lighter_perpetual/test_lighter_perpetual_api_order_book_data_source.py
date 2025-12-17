import asyncio
from decimal import Decimal
from typing import Any, Dict, List
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, call

from aioresponses import aioresponses

import hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_api_order_book_data_source import (
    LighterPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import LighterPerpetualDerivative
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class LighterPerpetualAPIOrderBookDataSourceTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.trading_pair = "BTC-USD"
        self.connector = MagicMock(spec=LighterPerpetualDerivative)
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="1")
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(
            return_value=self.trading_pair
        )
        self.connector.get_last_traded_prices = AsyncMock(
            return_value={self.trading_pair: 30000}
        )
        self.api_factory = MagicMock()
        self.rest_assistant = AsyncMock()
        self.api_factory.get_rest_assistant = AsyncMock(
            return_value=self.rest_assistant
        )
        self.ws_assistant = AsyncMock()
        self.api_factory.get_ws_assistant = AsyncMock(return_value=self.ws_assistant)
        self.data_source = LighterPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.api_factory,
        )

    def get_snapshot_payload(self) -> Dict[str, Any]:
        return {
            "timestamp": 1700000000,
            "offset": 1700000000,
            "bids": [{"price": "30000", "size": "1"}],
            "asks": [{"price": "30010", "size": "2"}],
        }

    @aioresponses()
    async def test_request_order_book_snapshot(self, mocked_api):
        url = web_utils.public_rest_url(
            CONSTANTS.ORDERBOOK_SNAPSHOT_URL, CONSTANTS.DEFAULT_DOMAIN
        )
        mocked_api.get(url, payload=self.get_snapshot_payload())
        self.rest_assistant.call.return_value = AsyncMock(
            status=200, json=AsyncMock(return_value=self.get_snapshot_payload())
        )
        order_book = await self.data_source.get_new_order_book(self.trading_pair)
        self.assertEqual(1700000000, order_book.snapshot_uid)

    async def test_subscribe_channels(self):
        ws_mock = AsyncMock()
        self.connector.exchange_symbol_associated_to_pair.return_value = "1"
        await self.data_source._subscribe_channels(ws_mock)
        sent_channels = [
            call.args[0].payload["channel"] for call in ws_mock.send.call_args_list
        ]
        expected_channels = {
            CONSTANTS.PUBLIC_WS_ORDER_BOOK_CHANNEL.format(market_id="1"),
            CONSTANTS.PUBLIC_WS_TRADES_CHANNEL.format(market_id="1"),
            CONSTANTS.PUBLIC_WS_MARKET_STATS_CHANNEL.format(market_id="1"),
        }
        self.assertEqual(expected_channels, set(sent_channels))

    async def test_parse_trade_message(self):
        queue = asyncio.Queue()
        event = {
            "channel": "trade:1",
            "type": "update/trade",
            "trades": [
                {
                    "trade_id": 10,
                    "market_id": 1,
                    "is_maker_ask": True,
                    "price": "30000",
                    "size": "1",
                    "timestamp": 1700000000,
                }
            ],
        }
        await self.data_source._parse_trade_message(event, queue)
        message = await queue.get()
        self.assertEqual(OrderBookMessageType.TRADE, message.type)

    async def test_parse_diff_message(self):
        queue = asyncio.Queue()
        event = {
            "channel": "order_book:1",
            "type": "update/order_book",
            "order_book": {
                "market_id": 1,
                "timestamp": 1700000000,
                "offset": 1700000100,
                "bids": [{"price": "30001", "size": "1"}],
                "asks": [{"price": "30002", "size": "1"}],
            },
        }
        await self.data_source._parse_order_book_diff_message(event, queue)
        message = await queue.get()
        self.assertEqual(OrderBookMessageType.DIFF, message.type)

    async def test_parse_funding_info_message(self):
        output = asyncio.Queue()
        event = {
            "channel": "market_stats:1",
            "type": "update/market_stats",
            "market_stats": {
                "market_id": 1,
                "current_funding_rate": "0.001",
                "mark_price": "30010",
                "index_price": "30000",
                "funding_timestamp": 1700003600,
            },
        }
        await self.data_source._parse_funding_info_message(event, output)
        message = await output.get()
        self.assertEqual(self.trading_pair, message.trading_pair)
        self.assertEqual(Decimal("0.001"), message.rate)
