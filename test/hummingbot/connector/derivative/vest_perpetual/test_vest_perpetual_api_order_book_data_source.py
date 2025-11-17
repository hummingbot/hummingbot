import asyncio
import sys
import types
from decimal import Decimal
from typing import Dict
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock


def ensure_module(name: str, attrs: Dict[str, object]):
    module = types.ModuleType(name)
    for attr_name, attr_value in attrs.items():
        setattr(module, attr_name, attr_value)
    sys.modules[name] = module


if "hummingbot.core.data_type.order_book" not in sys.modules:
    class _StubOrderBook:  # pragma: no cover - stub for optional dependency
        def apply_snapshot(self, *_, **__):
            pass

    ensure_module("hummingbot.core.data_type.order_book", {"OrderBook": _StubOrderBook})

if "hummingbot.core.data_type.limit_order" not in sys.modules:
    class _StubLimitOrder:  # pragma: no cover - stub for optional dependency
        def __init__(self, *_, **__):
            pass

    ensure_module("hummingbot.core.data_type.limit_order", {"LimitOrder": _StubLimitOrder})

if "hummingbot.connector.exchange_base" not in sys.modules:
    class _StubExchangeBase:  # pragma: no cover - stub for optional dependency
        def __init__(self, *_, **__):
            pass

    ensure_module("hummingbot.connector.exchange_base", {"ExchangeBase": _StubExchangeBase})

if "hummingbot.connector.trading_rule" not in sys.modules:
    class _StubTradingRule:  # pragma: no cover - stub for optional dependency
        def __init__(self, *_, **__):
            pass

    ensure_module("hummingbot.connector.trading_rule", {"TradingRule": _StubTradingRule})

if "hummingbot.core.network_iterator" not in sys.modules:
    class _StubNetworkStatus:  # pragma: no cover - stub for optional dependency
        CONNECTED = "CONNECTED"

    ensure_module("hummingbot.core.network_iterator", {"NetworkStatus": _StubNetworkStatus})

from hummingbot.connector.derivative.vest_perpetual import vest_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.vest_perpetual.vest_perpetual_api_order_book_data_source import (
    VestPerpetualAPIOrderBookDataSource,
)
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class _DummyConnector:
    def __init__(self):
        self._account_group = 3
        self.domain = CONSTANTS.DEFAULT_DOMAIN

    async def exchange_symbol_associated_to_pair(self, trading_pair: str) -> str:
        return trading_pair

    async def get_last_traded_prices(self, trading_pairs):
        return {pair: 1.0 for pair in trading_pairs}


class VestPerpetualAPIOrderBookDataSourceTests(IsolatedAsyncioTestCase):
    def setUp(self):
        super().setUp()
        self.connector = _DummyConnector()
        self.api_factory = MagicMock()
        self.rest_assistant = AsyncMock()
        self.api_factory.get_rest_assistant = AsyncMock(return_value=self.rest_assistant)
        self.ws_assistant = AsyncMock()
        self.ws_assistant.connect = AsyncMock()
        self.ws_assistant.send = AsyncMock()
        self.api_factory.get_ws_assistant = AsyncMock(return_value=self.ws_assistant)

        self.data_source = VestPerpetualAPIOrderBookDataSource(
            trading_pairs=["BTC-PERP"],
            connector=self.connector,
            api_factory=self.api_factory,
        )

    async def test_get_funding_info_returns_schema(self):
        response = {
            "tickers": [
                {
                    "symbol": "BTC-PERP",
                    "indexPrice": "100",
                    "markPrice": "101",
                    "oneHrFundingRate": "0.001",
                }
            ]
        }
        self.rest_assistant.execute_request = AsyncMock(return_value=response)

        info = await self.data_source.get_funding_info("BTC-PERP")

        self.assertEqual(Decimal("101"), info.mark_price)
        self.assertEqual(Decimal("0.001"), info.rate)

    async def test_order_book_snapshot_uses_rest_endpoint(self):
        depth = {"bids": [["100", "1"]], "asks": [["200", "2"]]}
        self.rest_assistant.execute_request = AsyncMock(return_value=depth)

        snapshot = await self.data_source._order_book_snapshot("BTC-PERP")

        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot.type)
        self.assertEqual("BTC-PERP", snapshot.content["trading_pair"])
        self.assertEqual([[Decimal("100"), Decimal("1")]], snapshot.content["bids"])

    async def test_channel_originating_message(self):
        snapshot_channel = self.data_source._channel_originating_message({"channel": "BTC-PERP@depth"})
        trade_channel = self.data_source._channel_originating_message({"channel": "BTC-PERP@trades"})
        funding_channel = self.data_source._channel_originating_message({"channel": CONSTANTS.WS_TICKERS_CHANNEL})

        self.assertEqual(self.data_source._diff_messages_queue_key, snapshot_channel)
        self.assertEqual(self.data_source._trade_messages_queue_key, trade_channel)
        self.assertEqual(self.data_source._funding_info_messages_queue_key, funding_channel)

    async def test_parse_order_book_diff_message_emits_message(self):
        queue: asyncio.Queue = asyncio.Queue()
        raw: Dict = {
            "channel": "BTC-PERP@depth",
            "data": {"bids": [["100", "1"]], "asks": [["101", "2"]], "time": 1},
        }

        await self.data_source._parse_order_book_diff_message(raw_message=raw, message_queue=queue)

        message = await queue.get()
        self.assertEqual(OrderBookMessageType.DIFF, message.type)
        self.assertEqual([[Decimal("100"), Decimal("1")]], message.content["bids"])

    async def test_parse_trade_message_emits_trade(self):
        queue: asyncio.Queue = asyncio.Queue()
        raw = {
            "channel": "BTC-PERP@trades",
            "data": {"id": "1", "price": "100", "qty": "2", "time": 2},
        }

        await self.data_source._parse_trade_message(raw_message=raw, message_queue=queue)

        trade = await queue.get()
        self.assertEqual(OrderBookMessageType.TRADE, trade.type)
        self.assertEqual(100.0, trade.content["price"])

    async def test_parse_funding_info_message_puts_updates(self):
        queue: asyncio.Queue = asyncio.Queue()
        raw = {
            "channel": CONSTANTS.WS_TICKERS_CHANNEL,
            "data": [
                {
                    "symbol": "BTC-PERP",
                    "indexPrice": "100",
                    "markPrice": "101",
                    "oneHrFundingRate": "0.002",
                }
            ],
        }

        await self.data_source._parse_funding_info_message(raw_message=raw, message_queue=queue)

        update = await queue.get()
        self.assertEqual("BTC-PERP", update.trading_pair)
        self.assertEqual(Decimal("0.002"), update.rate)

    async def test_subscribe_channels_sends_expected_requests(self):
        await self.data_source._subscribe_channels(self.ws_assistant)

        # One request for the pair and one for tickers
        self.assertEqual(2, self.ws_assistant.send.await_count)
        first_request = self.ws_assistant.send.await_args_list[0].args[0]
        self.assertIn("BTC-PERP@depth", first_request.payload["params"])
