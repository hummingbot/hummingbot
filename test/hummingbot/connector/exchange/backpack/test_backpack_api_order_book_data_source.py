import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.exchange.backpack import backpack_constants as CONSTANTS
from hummingbot.connector.exchange.backpack.backpack_api_order_book_data_source import (
    BackpackAPIOrderBookDataSource,
)
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class BackpackAPIOrderBookDataSourceTests(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.trading_pair = "BTC-USDC"
        self.exchange_symbol = "BTC_USDC"
        self.connector = MagicMock()
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.exchange_symbol)
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)
        self.connector.get_last_traded_prices = AsyncMock(return_value={self.trading_pair: 123.45})
        self.connector._api_get = AsyncMock()
        self.api_factory = MagicMock()
        self.data_source = BackpackAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.api_factory,
            domain=CONSTANTS.DOMAIN,
        )

    async def test_get_last_traded_prices_uses_rest_when_empty(self):
        self.data_source._last_traded_prices[self.trading_pair] = 0.0
        prices = await self.data_source.get_last_traded_prices([self.trading_pair])
        self.assertEqual(123.45, prices[self.trading_pair])
        self.connector.get_last_traded_prices.assert_awaited_once()

    async def test_subscribe_channels_sends_expected_payload(self):
        ws = AsyncMock()
        await self.data_source._subscribe_channels(ws)
        sent_request = ws.send.call_args[0][0]
        params = sent_request.payload["params"]
        self.assertIn(f"{CONSTANTS.WS_DEPTH_CHANNEL}.{self.exchange_symbol}", params)
        self.assertIn(f"{CONSTANTS.WS_TRADE_CHANNEL}.{self.exchange_symbol}", params)
        self.assertIn(f"{CONSTANTS.WS_TICKER_CHANNEL}.{self.exchange_symbol}", params)

    async def test_request_order_book_snapshot_calls_api(self):
        self.connector._api_get = AsyncMock(return_value={"bids": [], "asks": []})
        result = await self.data_source._request_order_book_snapshot(self.trading_pair)
        self.assertEqual({"bids": [], "asks": []}, result)
        self.connector._api_get.assert_awaited_once()
        kwargs = self.connector._api_get.call_args.kwargs
        self.assertEqual(CONSTANTS.DEPTH_URL, kwargs["path_url"])
        self.assertEqual({"symbol": self.exchange_symbol, "limit": 1000}, kwargs["params"])

    async def test_order_book_snapshot_returns_message(self):
        self.connector._api_get = AsyncMock(
            return_value={"lastUpdateId": 5, "bids": [["1", "2"]], "asks": [["3", "4"]]}
        )
        msg = await self.data_source._order_book_snapshot(self.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(self.trading_pair, msg.content["trading_pair"])
        self.assertEqual(5, msg.content["update_id"])

    async def test_connected_websocket_assistant_connects(self):
        ws = AsyncMock()
        self.api_factory.get_ws_assistant = AsyncMock(return_value=ws)
        result = await self.data_source._connected_websocket_assistant()
        self.assertEqual(ws, result)
        ws.connect.assert_awaited_once()

    async def test_parse_order_book_diff_message_puts_message(self):
        queue = asyncio.Queue()
        raw_message = {
            "stream": f"{CONSTANTS.WS_DEPTH_CHANNEL}.{self.exchange_symbol}",
            "data": {
                "b": [["1", "2"]],
                "a": [["1.1", "2.2"]],
                "u": 10,
                "T": 1_000_000,
            },
        }
        await self.data_source._parse_order_book_diff_message(raw_message, queue)
        msg = await queue.get()
        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(self.trading_pair, msg.content["trading_pair"])
        self.assertEqual(10, msg.content["update_id"])
        self.assertEqual([[1.0, 2.0]], msg.content["bids"])

    async def test_parse_order_book_snapshot_message_puts_message(self):
        queue = asyncio.Queue()
        raw_message = {
            "stream": f"{CONSTANTS.WS_DEPTH_CHANNEL}.{self.exchange_symbol}",
            "data": {
                "lastUpdateId": 99,
                "bids": [["1", "2"]],
                "asks": [["1.1", "2.2"]],
                "T": 1_000_000,
            },
        }
        await self.data_source._parse_order_book_snapshot_message(raw_message, queue)
        msg = await queue.get()
        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(self.trading_pair, msg.content["trading_pair"])
        self.assertEqual(99, msg.content["update_id"])

    async def test_parse_trade_message_updates_last_price(self):
        queue = asyncio.Queue()
        raw_message = {
            "stream": f"{CONSTANTS.WS_TRADE_CHANNEL}.{self.exchange_symbol}",
            "data": [
                {"p": "10", "q": "1", "m": False, "t": 1, "T": 1_000_000},
                {"p": "11", "q": "1", "m": True, "t": 2, "T": 1_000_000},
            ],
        }
        await self.data_source._parse_trade_message(raw_message, queue)
        msg_1 = await queue.get()
        msg_2 = await queue.get()
        self.assertEqual(OrderBookMessageType.TRADE, msg_1.type)
        self.assertEqual(OrderBookMessageType.TRADE, msg_2.type)
        self.assertEqual(11.0, self.data_source._last_traded_prices[self.trading_pair])

    async def test_parse_ticker_message_updates_last_price(self):
        self.data_source._last_traded_prices[self.trading_pair] = 55.0
        raw_message = {"data": {"s": self.exchange_symbol, "l": "123.4"}}
        await self.data_source._parse_ticker_message(raw_message)
        self.assertEqual(123.4, self.data_source._last_traded_prices[self.trading_pair])

    async def test_parse_ticker_message_ignores_missing_symbol(self):
        self.data_source._last_traded_prices[self.trading_pair] = 55.0
        await self.data_source._parse_ticker_message({"data": {"l": "99"}})
        self.assertEqual(55.0, self.data_source._last_traded_prices[self.trading_pair])

    def test_channel_originating_message(self):
        depth_message = {"stream": f"{CONSTANTS.WS_DEPTH_CHANNEL}.{self.exchange_symbol}", "data": {}}
        trade_message = {"stream": f"{CONSTANTS.WS_TRADE_CHANNEL}.{self.exchange_symbol}", "data": {}}
        ticker_message = {"stream": f"{CONSTANTS.WS_TICKER_CHANNEL}.{self.exchange_symbol}", "data": {}}
        event_message = {"data": {"e": CONSTANTS.DIFF_EVENT_TYPE}}

        self.assertEqual(CONSTANTS.DIFF_EVENT_TYPE, self.data_source._channel_originating_message(depth_message))
        self.assertEqual(CONSTANTS.TRADE_EVENT_TYPE, self.data_source._channel_originating_message(trade_message))
        self.assertEqual(CONSTANTS.WS_TICKER_CHANNEL, self.data_source._channel_originating_message(ticker_message))
        self.assertEqual(CONSTANTS.DIFF_EVENT_TYPE, self.data_source._channel_originating_message(event_message))
