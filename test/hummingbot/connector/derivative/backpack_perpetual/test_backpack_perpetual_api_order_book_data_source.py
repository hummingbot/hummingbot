import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.derivative.backpack_perpetual import backpack_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_api_order_book_data_source import (
    BackpackPerpetualAPIOrderBookDataSource,
)
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class BackpackPerpetualAPIOrderBookDataSourceTests(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.trading_pair = "BTC-USDC"
        self.exchange_symbol = "BTC_USDC_PERP"
        self.connector = MagicMock()
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.exchange_symbol)
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)
        self.connector.get_last_traded_prices = AsyncMock(return_value={self.trading_pair: 456.78})
        self.connector._api_get = AsyncMock()
        self.api_factory = MagicMock()
        self.data_source = BackpackPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.api_factory,
            domain=CONSTANTS.DOMAIN,
        )

    async def test_subscribe_channels_sends_expected_payload(self):
        ws = AsyncMock()
        await self.data_source._subscribe_channels(ws)
        sent_request = ws.send.call_args[0][0]
        params = sent_request.payload["params"]
        self.assertIn(f"{CONSTANTS.WS_DEPTH_CHANNEL}.{self.exchange_symbol}", params)
        self.assertIn(f"{CONSTANTS.WS_TRADE_CHANNEL}.{self.exchange_symbol}", params)
        self.assertIn(f"{CONSTANTS.WS_TICKER_CHANNEL}.{self.exchange_symbol}", params)
        self.assertIn(f"{CONSTANTS.WS_MARK_PRICE_CHANNEL}.{self.exchange_symbol}", params)

    async def test_parse_order_book_diff_message_puts_message(self):
        queue = asyncio.Queue()
        raw_message = {
            "stream": f"{CONSTANTS.WS_DEPTH_CHANNEL}.{self.exchange_symbol}",
            "data": {"b": [["1", "2"]], "a": [["1.1", "2.2"]], "u": 7, "T": 1_000_000},
        }
        await self.data_source._parse_order_book_diff_message(raw_message, queue)
        msg = await queue.get()
        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(self.trading_pair, msg.content["trading_pair"])
        self.assertEqual(7, msg.content["update_id"])

    async def test_parse_trade_message_updates_last_price(self):
        queue = asyncio.Queue()
        raw_message = {
            "stream": f"{CONSTANTS.WS_TRADE_CHANNEL}.{self.exchange_symbol}",
            "data": {"p": "101", "q": "0.5", "m": False, "t": 123, "T": 1_000_000},
        }
        await self.data_source._parse_trade_message(raw_message, queue)
        msg = await queue.get()
        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual(101.0, self.data_source._last_traded_prices[self.trading_pair])

    async def test_parse_funding_info_message_puts_update(self):
        queue = asyncio.Queue()
        raw_message = {
            "data": {
                "s": self.exchange_symbol,
                "p": "100",
                "i": "99",
                "f": "0.001",
                "n": 1_700_000_000_000,
            }
        }
        await self.data_source._parse_funding_info_message(raw_message, queue)
        update = await queue.get()
        self.assertEqual(self.trading_pair, update.trading_pair)
        self.assertEqual(Decimal("0.001"), update.rate)
        self.assertEqual(Decimal("100"), update.mark_price)
        self.assertEqual(Decimal("99"), update.index_price)

    async def test_get_funding_info_uses_rest_data(self):
        funding_data = [{
            "symbol": self.exchange_symbol,
            "fundingRate": "0.002",
            "nextFundingTime": 1_700_000_000_000,
        }]
        mark_price_data = [{
            "symbol": self.exchange_symbol,
            "markPrice": "100.5",
            "indexPrice": "100.0",
        }]
        self.connector._api_get = AsyncMock(side_effect=[funding_data, mark_price_data])
        info = await self.data_source.get_funding_info(self.trading_pair)
        self.assertEqual(self.trading_pair, info.trading_pair)
        self.assertEqual(Decimal("0.002"), info.rate)
        self.assertEqual(Decimal("100.5"), info.mark_price)

    async def test_order_book_snapshot_returns_message(self):
        self.connector._api_get = AsyncMock(
            return_value={"lastUpdateId": 11, "bids": [["1", "2"]], "asks": [["3", "4"]]}
        )
        msg = await self.data_source._order_book_snapshot(self.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(11, msg.content["update_id"])

    async def test_get_last_traded_prices_uses_rest_when_empty(self):
        self.data_source._last_traded_prices[self.trading_pair] = 0.0
        prices = await self.data_source.get_last_traded_prices([self.trading_pair])
        self.assertEqual(456.78, prices[self.trading_pair])

    async def test_get_funding_info_uses_next_funding_fallback(self):
        self.connector._api_get = AsyncMock(side_effect=[[], []])
        with patch.object(self.data_source, "_next_funding_time", return_value=123456):
            info = await self.data_source.get_funding_info(self.trading_pair)
        self.assertEqual(123456, info.next_funding_utc_timestamp)

    async def test_parse_ticker_message_updates_last_price(self):
        raw_message = {"data": {"s": self.exchange_symbol, "l": "202.5"}}
        await self.data_source._parse_ticker_message(raw_message)
        self.assertEqual(202.5, self.data_source._last_traded_prices[self.trading_pair])

    def test_next_funding_time_calculation(self):
        with patch(
            "hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_api_order_book_data_source.time.time",
            return_value=0,
        ):
            next_funding = self.data_source._next_funding_time()
        self.assertEqual(8 * 60 * 60, next_funding)

    def test_channel_originating_message_mark_price(self):
        mark_message = {"stream": f"{CONSTANTS.WS_MARK_PRICE_CHANNEL}.{self.exchange_symbol}", "data": {}}
        channel = self.data_source._channel_originating_message(mark_message)
        self.assertEqual(self.data_source._funding_info_messages_queue_key, channel)
