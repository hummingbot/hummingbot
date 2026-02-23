import asyncio
import time
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from bidict import bidict

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_api_order_book_data_source import (
    GrvtPerpetualAPIOrderBookDataSource,
)
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class GrvtPerpetualAPIOrderBookDataSourceTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = "BTC_USDT_Perp"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None

        self.connector = MagicMock()
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)

        self.api_factory = MagicMock()
        self.data_source = GrvtPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.api_factory,
            domain=CONSTANTS.DOMAIN,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

    def tearDown(self) -> None:
        if self.listening_task is not None:
            self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    async def test_get_last_traded_prices(self):
        mock_prices = {self.trading_pair: 50000.0}
        self.connector.get_last_traded_prices = AsyncMock(return_value=mock_prices)

        result = await self.data_source.get_last_traded_prices(
            trading_pairs=[self.trading_pair],
        )
        self.assertEqual(mock_prices, result)

    async def test_get_funding_info(self):
        funding_response = {
            "result": [
                {
                    "index_price": "50000.0",
                    "mark_price": "50010.0",
                    "funding_rate": "0.0001",
                }
            ]
        }
        self.connector._api_post = AsyncMock(return_value=funding_response)

        funding_info = await self.data_source.get_funding_info(self.trading_pair)

        self.assertIsInstance(funding_info, FundingInfo)
        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal("50000.0"), funding_info.index_price)
        self.assertEqual(Decimal("50010.0"), funding_info.mark_price)
        self.assertEqual(Decimal("0.0001"), funding_info.rate)

    async def test_get_funding_info_error_returns_zeros(self):
        self.connector._api_post = AsyncMock(side_effect=Exception("API error"))

        funding_info = await self.data_source.get_funding_info(self.trading_pair)

        self.assertIsInstance(funding_info, FundingInfo)
        self.assertEqual(Decimal("0"), funding_info.index_price)
        self.assertEqual(Decimal("0"), funding_info.mark_price)
        self.assertEqual(Decimal("0"), funding_info.rate)

    async def test_request_order_book_snapshot(self):
        snapshot_response = {
            "result": {
                "bids": [{"price": "49990", "size": "1.5"}],
                "asks": [{"price": "50010", "size": "2.0"}],
            }
        }
        self.connector._api_post = AsyncMock(return_value=snapshot_response)

        result = await self.data_source._request_order_book_snapshot(self.trading_pair)

        self.assertEqual(snapshot_response, result)
        self.connector._api_post.assert_called_once_with(
            path_url=CONSTANTS.ORDERBOOK_URL,
            data={"instrument": self.ex_trading_pair, "depth": 20},
        )

    async def test_order_book_snapshot_message(self):
        snapshot_response = {
            "result": {
                "bids": [{"price": "49990", "size": "1.5"}, {"price": "49980", "size": "3.0"}],
                "asks": [{"price": "50010", "size": "2.0"}, {"price": "50020", "size": "1.0"}],
            }
        }
        self.connector._api_post = AsyncMock(return_value=snapshot_response)

        snapshot_msg = await self.data_source._order_book_snapshot(self.trading_pair)

        self.assertIsInstance(snapshot_msg, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_msg.type)
        self.assertEqual(self.trading_pair, snapshot_msg.content["trading_pair"])
        self.assertEqual(2, len(snapshot_msg.content["bids"]))
        self.assertEqual(2, len(snapshot_msg.content["asks"]))
        self.assertEqual(49990.0, snapshot_msg.content["bids"][0][0])
        self.assertEqual(1.5, snapshot_msg.content["bids"][0][1])

    def test_channel_originating_message_book(self):
        msg = {"channel": "book.s", "data": {}}
        channel = self.data_source._channel_originating_message(msg)
        self.assertEqual("order_book_snapshot", channel)

    def test_channel_originating_message_trade(self):
        msg = {"channel": "trade", "data": {}}
        channel = self.data_source._channel_originating_message(msg)
        self.assertEqual(self.data_source._trade_messages_queue_key, channel)

    def test_channel_originating_message_ticker(self):
        msg = {"channel": "ticker.s", "data": {}}
        channel = self.data_source._channel_originating_message(msg)
        self.assertEqual("funding_info", channel)

    def test_channel_originating_message_error(self):
        msg = {"error": "some error"}
        channel = self.data_source._channel_originating_message(msg)
        self.assertEqual("", channel)

    def test_parse_instrument_from_message_dict(self):
        msg = {"data": {"instrument": "BTC_USDT_Perp"}}
        instrument = self.data_source._parse_instrument_from_message(msg)
        self.assertEqual("BTC_USDT_Perp", instrument)

    def test_parse_instrument_from_message_list(self):
        msg = {"data": [{"instrument": "ETH_USDT_Perp"}]}
        instrument = self.data_source._parse_instrument_from_message(msg)
        self.assertEqual("ETH_USDT_Perp", instrument)

    def test_parse_instrument_from_message_empty(self):
        msg = {"data": {}}
        instrument = self.data_source._parse_instrument_from_message(msg)
        self.assertEqual("", instrument)

    def test_next_funding_time(self):
        result = self.data_source._next_funding_time()
        self.assertIsInstance(result, int)
        self.assertGreater(result, time.time())
        # Should be within 8 hours from now
        self.assertLessEqual(result - time.time(), 8 * 3600)

    async def test_parse_order_book_diff_message(self):
        raw_message = {
            "channel": "book.d",
            "data": {
                "instrument": "BTC_USDT_Perp",
                "timestamp": str(int(time.time() * 1e3)),
                "bids": [{"price": "49990", "size": "1.0"}],
                "asks": [{"price": "50010", "size": "2.0"}],
            },
        }
        message_queue = asyncio.Queue()
        await self.data_source._parse_order_book_diff_message(raw_message, message_queue)

        self.assertFalse(message_queue.empty())
        msg = message_queue.get_nowait()
        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(self.trading_pair, msg.content["trading_pair"])

    async def test_parse_trade_message(self):
        raw_message = {
            "channel": "trade",
            "data": {
                "instrument": "BTC_USDT_Perp",
                "trade_id": "12345",
                "price": "50000",
                "size": "0.1",
                "side": "BUY",
                "timestamp": str(int(time.time() * 1e3)),
            },
        }
        message_queue = asyncio.Queue()
        await self.data_source._parse_trade_message(raw_message, message_queue)

        self.assertFalse(message_queue.empty())
        msg = message_queue.get_nowait()
        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual("12345", msg.content["trade_id"])
        self.assertEqual(50000.0, msg.content["price"])
        self.assertEqual(0.1, msg.content["amount"])
