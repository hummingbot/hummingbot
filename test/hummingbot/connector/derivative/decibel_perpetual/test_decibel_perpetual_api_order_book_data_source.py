import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock

import aiohttp

from hummingbot.connector.derivative.decibel_perpetual import decibel_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_api_order_book_data_source import (
    DecibelPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection
from hummingbot.core.web_assistant.connections.ws_connection import WSConnection
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class DecibelPerpetualAPIOrderBookDataSourceTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.exchange_symbol = f"{cls.base_asset}/{cls.quote_asset}"
        cls.market_addr = "0xmarketaddr123"

    def setUp(self):
        super().setUp()
        self.log_records = []
        self.async_tasks = []

        self.connector = MagicMock()
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(side_effect=lambda trading_pair: trading_pair.replace("-", "/"))
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(side_effect=lambda symbol: symbol.replace("/", "-"))
        self.connector.get_last_traded_prices = AsyncMock(return_value={"BTC-USD": 50000.0})
        self.connector._trading_pairs = [self.trading_pair]
        self.connector.api_key = "test_api_key"
        self.connector.get_market_addr_for_pair = AsyncMock(return_value=self.market_addr)
        self.connector.get_perp_engine_global_address = AsyncMock(return_value="0xperpengine123")
        self.connector._market_info = {self.trading_pair: {"market_addr": self.market_addr}}

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.async_tasks = []

        self.client_session = aiohttp.ClientSession(loop=self.local_event_loop)
        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.rest_connection = RESTConnection(self.client_session)
        self.rest_assistant = RESTAssistant(connection=self.rest_connection, throttler=self.throttler)
        self.ws_connection = WSConnection(self.client_session)
        self.ws_assistant = WSAssistant(connection=self.ws_connection)

        self.api_factory = MagicMock()
        self.api_factory.get_ws_assistant = AsyncMock(return_value=self.ws_assistant)
        self.api_factory.get_rest_assistant = AsyncMock(return_value=self.rest_assistant)

        self.data_source = DecibelPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.api_factory,
            domain=CONSTANTS.DEFAULT_DOMAIN,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        await self.mocking_assistant.async_init()

    def tearDown(self):
        self.run_async_with_timeout(self.client_session.close())
        for task in self.async_tasks:
            task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str):
        return any(record.levelname == log_level and message in record.getMessage() for record in self.log_records)

    def get_funding_info_msg(self):
        return {
            "funding_rate_bps": 5,
            "mark_px": "50120.5",
            "oracle_px": "50100.0",
        }

    async def test_order_book_snapshot(self):
        message = await self.data_source._order_book_snapshot(trading_pair=self.trading_pair)

        self.assertIsInstance(message, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, message.type)
        self.assertEqual(self.trading_pair, message.content["trading_pair"])
        self.assertEqual([], message.content["bids"])
        self.assertEqual([], message.content["asks"])
        self.connector.get_market_addr_for_pair.assert_awaited_once_with(self.trading_pair)

    async def test_get_funding_info_successful(self):
        self.api_factory.get_rest_assistant = AsyncMock()
        mock_response = [self.get_funding_info_msg()]
        self.api_factory.get_rest_assistant.return_value.execute_request = AsyncMock(return_value=mock_response)

        funding_info = await self.data_source.get_funding_info(trading_pair=self.trading_pair)

        self.assertIsInstance(funding_info, FundingInfo)
        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal("50120.5"), funding_info.mark_price)
        self.assertEqual(Decimal("50100.0"), funding_info.index_price)
        self.assertAlmostEqual(Decimal("0.0005"), funding_info.rate, places=6)

    async def test_get_last_traded_prices(self):
        self.connector.get_last_traded_prices.return_value = {"BTC-USD": 50000.0, "ETH-USD": 3000.0}
        result = await self.data_source.get_last_traded_prices(["BTC-USD", "ETH-USD"])
        self.assertEqual({"BTC-USD": 50000.0, "ETH-USD": 3000.0}, result)
        self.connector.get_last_traded_prices.assert_awaited_once_with(trading_pairs=["BTC-USD", "ETH-USD"])

    async def test_get_headers_with_api_key(self):
        self.connector.api_key = "test_key"
        headers = self.data_source._get_headers()
        self.assertEqual({"Authorization": "Bearer test_key"}, headers)

    async def test_get_headers_without_api_key(self):
        self.connector.api_key = None
        headers = self.data_source._get_headers()
        self.assertEqual({}, headers)

    async def test_order_book_snapshot_maps_market_addr(self):
        await self.data_source._order_book_snapshot(trading_pair=self.trading_pair)

        self.assertEqual(self.trading_pair, self.data_source._market_addr_to_trading_pair.get(self.market_addr))

    async def test_channel_originating_message_depth(self):
        msg = {"topic": f"depth:{self.market_addr}:1", "bids": [], "asks": []}
        result = self.data_source._channel_originating_message(msg)
        self.assertEqual(self.data_source._snapshot_messages_queue_key, result)

    async def test_channel_originating_message_trades(self):
        msg = {"topic": f"trades:{self.market_addr}", "trades": []}
        result = self.data_source._channel_originating_message(msg)
        self.assertEqual(self.data_source._trade_messages_queue_key, result)

    async def test_channel_originating_message_funding(self):
        msg = {"topic": f"market_price:{self.market_addr}", "price": {}}
        result = self.data_source._channel_originating_message(msg)
        self.assertEqual(self.data_source._funding_info_messages_queue_key, result)

    async def test_channel_originating_message_unknown(self):
        msg = {"topic": "unknown_channel"}
        result = self.data_source._channel_originating_message(msg)
        self.assertEqual("", result)

    async def test_parse_order_book_snapshot_message(self):
        message_queue = asyncio.Queue()
        raw_message = {
            "topic": f"depth:{self.market_addr}:1",
            "bids": [{"price": "50000", "size": "1.5"}, {"price": "49900", "size": "2.0"}],
            "asks": [{"price": "50100", "size": "1.0"}],
        }
        self.data_source._market_addr_to_trading_pair[self.market_addr] = self.trading_pair

        await self.data_source._parse_order_book_snapshot_message(raw_message, message_queue)

        self.assertEqual(1, message_queue.qsize())
        msg = message_queue.get_nowait()
        self.assertIsInstance(msg, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(self.trading_pair, msg.content["trading_pair"])
        self.assertEqual(2, len(msg.content["bids"]))
        self.assertEqual(1, len(msg.content["asks"]))

    async def test_parse_order_book_snapshot_message_list_format(self):
        """Test parsing order book with list [price, size] format."""
        message_queue = asyncio.Queue()
        raw_message = {
            "topic": f"depth:{self.market_addr}:1",
            "bids": [["50000", "1.5"]],
            "asks": [["50100", "1.0"]],
        }
        self.data_source._market_addr_to_trading_pair[self.market_addr] = self.trading_pair

        await self.data_source._parse_order_book_snapshot_message(raw_message, message_queue)

        self.assertEqual(1, message_queue.qsize())
        msg = message_queue.get_nowait()
        self.assertEqual([("50000", "1.5")], msg.content["bids"])

    async def test_parse_order_book_snapshot_message_unknown_market(self):
        message_queue = asyncio.Queue()
        raw_message = {
            "topic": "depth:0xunknown:1",
            "bids": [],
            "asks": [],
        }

        await self.data_source._parse_order_book_snapshot_message(raw_message, message_queue)

        self.assertEqual(0, message_queue.qsize())
        self.assertTrue(
            self._is_logged("WARNING", "Unknown market address in orderbook message: 0xunknown")
        )

    async def test_parse_trade_message(self):
        message_queue = asyncio.Queue()
        raw_message = {
            "topic": f"trades:{self.market_addr}",
            "trades": [
                {
                    "trade_id": 123,
                    "price": "50100",
                    "size": "0.8",
                    "action": "long",
                    "unix_ms": 1700000000000,
                }
            ],
        }
        self.data_source._market_addr_to_trading_pair[self.market_addr] = self.trading_pair

        await self.data_source._parse_trade_message(raw_message, message_queue)

        self.assertEqual(1, message_queue.qsize())
        msg = message_queue.get_nowait()
        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual(self.trading_pair, msg.content["trading_pair"])
        self.assertEqual("50100", msg.content["price"])
        self.assertEqual("0.8", msg.content["amount"])

    async def test_parse_trade_message_sell(self):
        message_queue = asyncio.Queue()
        raw_message = {
            "topic": f"trades:{self.market_addr}",
            "trades": [
                {
                    "trade_id": 456,
                    "price": "50000",
                    "size": "1.0",
                    "action": "short",
                    "unix_ms": 1700000000000,
                }
            ],
        }
        self.data_source._market_addr_to_trading_pair[self.market_addr] = self.trading_pair

        await self.data_source._parse_trade_message(raw_message, message_queue)

        msg = message_queue.get_nowait()
        self.assertEqual(TradeType.SELL.value, msg.content["trade_type"])

    async def test_parse_funding_info_message(self):
        message_queue = asyncio.Queue()
        raw_message = {
            "topic": f"market_price:{self.market_addr}",
            "price": {
                "funding_rate_bps": 10,
            },
        }
        self.data_source._market_addr_to_trading_pair[self.market_addr] = self.trading_pair

        await self.data_source._parse_funding_info_message(raw_message, message_queue)

        self.assertGreater(message_queue.qsize(), 0)
        msg = message_queue.get_nowait()
        self.assertIsInstance(msg, FundingInfoUpdate)
        self.assertEqual(self.trading_pair, msg.trading_pair)
        self.assertEqual(Decimal("0.001"), msg.rate)

    async def test_parse_funding_info_message_unknown_market(self):
        message_queue = asyncio.Queue()
        raw_message = {
            "topic": "market_price:0xunknown",
            "price": {"funding_rate_bps": 10},
        }

        await self.data_source._parse_funding_info_message(raw_message, message_queue)

        self.assertEqual(0, message_queue.qsize())

    async def test_subscribe_to_trading_pair(self):
        mock_ws = AsyncMock()
        self.data_source._ws_assistant = mock_ws

        await self.data_source.subscribe_to_trading_pair(self.trading_pair)

        self.assertEqual(3, mock_ws.send.call_count)

    async def test_subscribe_to_trading_pair_no_ws(self):
        self.data_source._ws_assistant = None
        await self.data_source.subscribe_to_trading_pair(self.trading_pair)

    async def test_unsubscribe_from_trading_pair(self):
        mock_ws = AsyncMock()
        self.data_source._ws_assistant = mock_ws

        await self.data_source.unsubscribe_from_trading_pair(self.trading_pair)

        self.assertEqual(3, mock_ws.send.call_count)

    async def test_unsubscribe_from_trading_pair_no_ws(self):
        self.data_source._ws_assistant = None
        await self.data_source.unsubscribe_from_trading_pair(self.trading_pair)

    async def test_get_funding_info_with_empty_response(self):
        self.api_factory.get_rest_assistant = AsyncMock()
        self.api_factory.get_rest_assistant.return_value.execute_request = AsyncMock(return_value=[])

        with self.assertRaises(Exception):
            await self.data_source.get_funding_info(self.trading_pair)

    async def test_process_message_for_unknown_channel(self):
        mock_ws = AsyncMock()
        msg = {"topic": "unknown", "data": {}}
        # Should not raise
        await self.data_source._process_message_for_unknown_channel(msg, mock_ws)

    async def test_parse_trade_message_unknown_market(self):
        message_queue = asyncio.Queue()
        raw_message = {
            "topic": "trades:0xunknown",
            "trades": [{"trade_id": 1, "price": "50000", "size": "1.0"}],
        }
        await self.data_source._parse_trade_message(raw_message, message_queue)
        self.assertEqual(0, message_queue.qsize())

    async def test_order_book_snapshot_exception(self):
        """Test order book snapshot when everything fails."""
        self.connector.get_market_addr_for_pair = AsyncMock(side_effect=Exception("fail"))

        # Should still return a snapshot (exception is caught internally)
        message = await self.data_source._order_book_snapshot(trading_pair=self.trading_pair)
        self.assertIsInstance(message, OrderBookMessage)
