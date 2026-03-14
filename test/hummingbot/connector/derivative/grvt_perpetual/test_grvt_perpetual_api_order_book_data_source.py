import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_api_order_book_data_source import (
    GRVTPerpetualAPIOrderBookDataSource,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class GRVTPerpetualAPIOrderBookDataSourceTests(TestCase):
    def setUp(self):
        self.connector = MagicMock()
        self.connector.get_last_traded_prices = AsyncMock(return_value={"BTC-USDT": 50000.0})
        
        self.data_source = GRVTPerpetualAPIOrderBookDataSource(
            trading_pairs=["BTC-USDT"],
            connector=self.connector,
            api_factory=MagicMock(),
            domain="grvt_perpetual",
        )

    def async_run_with_timeout(self, coroutine, timeout: int = 1):
        return asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_get_last_traded_prices(self):
        prices = self.async_run_with_timeout(
            self.data_source.get_last_traded_prices(["BTC-USDT"])
        )
        self.assertEqual({"BTC-USDT": 50000.0}, prices)


class GRVTPerpetualAPIOrderBookDataSourceAsyncTests(IsolatedAsyncioWrapperTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    async def asyncSetUp(self):
        await super().asyncSetUp()
        
        self.connector = MagicMock()
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.connector.trading_pair_associated_to_exchange_symbol = MagicMock(return_value=self.trading_pair)
        self.connector.get_last_traded_prices = AsyncMock(return_value={self.trading_pair: 50000.0})
        
        self.data_source = GRVTPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=MagicMock(),
            domain="grvt_perpetual",
        )

    async def test_get_funding_info(self):
        self.connector._api_get = AsyncMock(return_value={
            "symbol": "BTC-USDT",
            "markPrice": "50000.0",
            "indexPrice": "49900.0",
            "lastFundingRate": "0.0001",
            "nextFundingTime": "1700000000000",
        })
        
        funding_info = await self.data_source.get_funding_info(self.trading_pair)
        
        self.assertIsInstance(funding_info, FundingInfo)
        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal("49900"), funding_info.index_price)
        self.assertEqual(Decimal("50000"), funding_info.mark_price)

    async def test_order_book_snapshot(self):
        self.connector._api_get = AsyncMock(return_value={
            "lastUpdateId": 12345,
            "bids": [["50000", "1.0"], ["49999", "2.0"]],
            "asks": [["50001", "1.5"], ["50002", "3.0"]],
        })
        
        snapshot = await self.data_source._order_book_snapshot(self.trading_pair)
        
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot.type)
        self.assertEqual(self.trading_pair, snapshot.content["trading_pair"])
        self.assertEqual(2, len(snapshot.content["bids"]))
        self.assertEqual(2, len(snapshot.content["asks"]))

    async def test_parse_order_book_diff_message(self):
        raw_message = {
            "stream": "btc-usdt:depth",
            "data": {
                "s": "BTC-USDT",
                "u": 12345,
                "b": [["50000", "1.0"]],
                "a": [["50001", "1.5"]],
            }
        }
        
        message_queue = asyncio.Queue()
        await self.data_source._parse_order_book_diff_message(raw_message, message_queue)
        
        self.assertFalse(message_queue.empty())
        diff_message = await message_queue.get()
        self.assertEqual(OrderBookMessageType.DIFF, diff_message.type)

    async def test_parse_trade_message(self):
        raw_message = {
            "stream": "btc-usdt:trade",
            "data": {
                "s": "BTC-USDT",
                "t": 12345,
                "p": "50000",
                "q": "1.0",
                "m": False,  # false = buy
                "E": 1700000000000,
            }
        }
        
        message_queue = asyncio.Queue()
        await self.data_source._parse_trade_message(raw_message, message_queue)
        
        self.assertFalse(message_queue.empty())
        trade_message = await message_queue.get()
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)

    async def test_parse_funding_info_message(self):
        raw_message = {
            "stream": "btc-usdt:mark_price",
            "data": {
                "s": "BTC-USDT",
                "i": "49900",
                "p": "50000",
                "r": "0.0001",
                "T": 1700000000000,
            }
        }
        
        message_queue = asyncio.Queue()
        await self.data_source._parse_funding_info_message(raw_message, message_queue)
        
        self.assertFalse(message_queue.empty())

    async def test_channel_originating_message(self):
        # Test depth channel
        depth_message = {"stream": "btc-usdt:depth", "data": {}}
        channel = self.data_source._channel_originating_message(depth_message)
        self.assertEqual(str(CONSTANTS.DIFF_STREAM_ID), channel)
        
        # Test trade channel
        trade_message = {"stream": "btc-usdt:trade", "data": {}}
        channel = self.data_source._channel_originating_message(trade_message)
        self.assertEqual(str(CONSTANTS.TRADE_STREAM_ID), channel)
        
        # Test funding channel
        funding_message = {"stream": "btc-usdt:mark_price", "data": {}}
        channel = self.data_source._channel_originating_message(funding_message)
        self.assertEqual(str(CONSTANTS.FUNDING_INFO_STREAM_ID), channel)
