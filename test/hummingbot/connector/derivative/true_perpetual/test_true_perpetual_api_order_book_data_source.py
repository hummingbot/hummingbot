import asyncio
import json
import re
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

from hummingbot.connector.derivative.true_perpetual import (
    true_perpetual_constants as CONSTANTS,
    true_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.true_perpetual.true_perpetual_api_order_book_data_source import (
    TruePerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.true_perpetual.true_perpetual_derivative import TruePerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class TruePerpetualAPIOrderBookDataSourceTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"
        cls.domain = CONSTANTS.DOMAIN

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)

        self.connector = TruePerpetualDerivative(
            true_perpetual_api_key="",
            true_perpetual_api_secret="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
            domain=self.domain,
        )
        self.connector._time_synchronizer.add_time_offset_ms_sample(0)
        self.data_source = TruePerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain,
        )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)
        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1
        self.resume_test_event = asyncio.Event()
        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    # ── fixtures ────────────────────────────────────────────────────────────

    def _snapshot_rest_response(self):
        return {
            "ok": True,
            "data": {
                "market": self.ex_trading_pair,
                "bids": {"81000": "0.5", "81500": "0.25", "80000": "1"},
                "asks": {"82500": "0.3", "82000": "0.1", "83000": "2"},
            },
        }

    def _ws_snapshot_event(self):
        return {
            "topic": f"orderbook:{self.ex_trading_pair}",
            "type": "snapshot",
            "ts": 1700000000000,
            "data": {"u": 77, "bids": [["81000", "0.5"], ["81500", "0.25"]], "asks": [["82500", "0.3"], ["82000", "0.1"]]},
        }

    def _ws_diff_event(self):
        return {
            "topic": f"orderbook:{self.ex_trading_pair}",
            "type": "delta",
            "ts": 1700000001000,
            "data": {"u": 78, "bids": [["81200", "0.4"]], "asks": [["82100", "0"]]},
        }

    def _ws_trade_event(self):
        return {
            "topic": f"trades:{self.ex_trading_pair}",
            "type": "delta",
            "ts": 1700000002000,
            "data": [
                {"id": "177396390-1", "price": "82000", "size": "0.002", "side": "buy", "created_at": 1700000002000},
                {"id": "177396391-1", "price": "81990", "size": "0.001", "side": "sell", "created_at": 1700000002500},
            ],
        }

    def _ws_mark_event(self):
        return {
            "topic": f"mark:{self.ex_trading_pair}",
            "type": "update",
            "ts": 1700000003000,
            "data": {"market": self.ex_trading_pair, "mark_price": "82050.5"},
        }

    # ── helpers ─────────────────────────────────────────────────────────────

    def test_levels_sorts_dict_books(self):
        bids = TruePerpetualAPIOrderBookDataSource._levels({"81000": "0.5", "81500": "0.25", "80000": "1"}, descending=True)
        self.assertEqual([["81500", "0.25"], ["81000", "0.5"], ["80000", "1"]], bids)
        asks = TruePerpetualAPIOrderBookDataSource._levels({"82500": "0.3", "82000": "0.1", "83000": "2"})
        self.assertEqual([["82000", "0.1"], ["82500", "0.3"], ["83000", "2"]], asks)

    def test_levels_handles_lists_and_empty(self):
        self.assertEqual([], TruePerpetualAPIOrderBookDataSource._levels(None))
        self.assertEqual([["1", "2"], ["3", "4"]], TruePerpetualAPIOrderBookDataSource._levels([[3, 4], [1, 2]]))

    def test_next_funding_timestamp_is_next_8h_boundary(self):
        self.assertEqual(8 * 3600, TruePerpetualAPIOrderBookDataSource._next_funding_timestamp(now=1))
        self.assertEqual(16 * 3600, TruePerpetualAPIOrderBookDataSource._next_funding_timestamp(now=8 * 3600))
        self.assertEqual(16 * 3600, TruePerpetualAPIOrderBookDataSource._next_funding_timestamp(now=8 * 3600 + 5))

    def test_channel_originating_message(self):
        self.assertEqual("orderbook_snapshot", self.data_source._channel_originating_message(self._ws_snapshot_event()))
        self.assertEqual("orderbook_delta", self.data_source._channel_originating_message(self._ws_diff_event()))
        self.assertEqual("trades", self.data_source._channel_originating_message(self._ws_trade_event()))
        self.assertEqual("mark", self.data_source._channel_originating_message(self._ws_mark_event()))
        self.assertEqual("", self.data_source._channel_originating_message({"op": "ping"}))

    # ── REST ────────────────────────────────────────────────────────────────

    @aioresponses()
    async def test_get_last_traded_prices(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.TICKER_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, body=json.dumps({
            "ok": True,
            "data": {"results": [
                {"symbol": self.ex_trading_pair, "last_traded_price": "82012.5", "volume_24h": "10"},
                {"symbol": "ETHUSDC", "last_traded_price": "3000"},
            ]},
        }))
        prices = await self.data_source.get_last_traded_prices([self.trading_pair])
        self.assertEqual({self.trading_pair: 82012.5}, prices)

    @aioresponses()
    async def test_get_new_order_book_successful(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.ORDERBOOK_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, body=json.dumps(self._snapshot_rest_response()))

        order_book: OrderBook = await self.data_source.get_new_order_book(self.trading_pair)

        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(3, len(bids))
        self.assertEqual(3, len(asks))
        self.assertEqual(81500, bids[0].price)
        self.assertEqual(0.25, bids[0].amount)
        self.assertEqual(82000, asks[0].price)
        self.assertEqual(0.1, asks[0].amount)
        self.assertEqual(bids[0].update_id, asks[0].update_id)

    @aioresponses()
    async def test_get_new_order_book_raises_exception(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.ORDERBOOK_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            await self.data_source.get_new_order_book(self.trading_pair)

    @aioresponses()
    async def test_get_funding_info(self, mock_api):
        markets_url = web_utils.public_rest_url(CONSTANTS.MARKETS_PATH_URL, domain=self.domain)
        mock_api.get(markets_url, body=json.dumps({"ok": True, "markets": [
            {"symbol": self.ex_trading_pair, "base": "BTC", "quote": "USDC", "active": True,
             "lotSize": "0.001", "tickSize": "1", "fundingRate8h": "0.0001"},
        ]}))
        mark_url = web_utils.public_rest_url(CONSTANTS.MARK_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{mark_url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, body=json.dumps({"ok": True, "market": self.ex_trading_pair, "mark": "82050.5"}))

        funding_info: FundingInfo = await self.data_source.get_funding_info(self.trading_pair)

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal("82050.5"), funding_info.mark_price)
        self.assertEqual(Decimal("82050.5"), funding_info.index_price)
        self.assertEqual(Decimal("0.0001"), funding_info.rate)
        self.assertEqual(0, funding_info.next_funding_utc_timestamp % CONSTANTS.FUNDING_INTERVAL_SECONDS)

    # ── websocket ───────────────────────────────────────────────────────────

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_subscribes_to_channels(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps({"op": "subscribe", "ok": True}))

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent = self.mocking_assistant.json_messages_sent_through_websocket(websocket_mock=ws_connect_mock.return_value)
        self.assertEqual(1, len(sent))
        self.assertEqual({
            "op": "subscribe",
            "args": [f"orderbook:{self.ex_trading_pair}", f"trades:{self.ex_trading_pair}", f"mark:{self.ex_trading_pair}"],
        }, sent[0])
        self.assertTrue(self._is_logged("INFO", "Subscribed to TRUE order book, trades and mark price channels..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_sends_bearer_token_when_available(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.connector.ws_token = AsyncMock(return_value="tok_123")
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps({"op": "subscribe", "ok": True}))

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        headers = ws_connect_mock.call_args.kwargs.get("headers") or {}
        self.assertEqual("Bearer tok_123", headers.get("Authorization"))
        self.assertEqual(CONSTANTS.WSS_URL, ws_connect_mock.call_args.args[0] if ws_connect_mock.call_args.args
                         else ws_connect_mock.call_args.kwargs.get("url"))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_answers_ping_with_pong(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps({"op": "ping"}))

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent = self.mocking_assistant.json_messages_sent_through_websocket(websocket_mock=ws_connect_mock.return_value)
        self.assertIn({"op": "pong"}, sent)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_routes_messages_to_queues(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        for event in (self._ws_snapshot_event(), self._ws_diff_event(), self._ws_trade_event(), self._ws_mark_event()):
            self.mocking_assistant.add_websocket_aiohttp_message(
                websocket_mock=ws_connect_mock.return_value, message=json.dumps(event))

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(1, self.data_source._message_queue["orderbook_snapshot"].qsize())
        self.assertEqual(1, self.data_source._message_queue["orderbook_delta"].qsize())
        self.assertEqual(1, self.data_source._message_queue["trades"].qsize())
        self.assertEqual(1, self.data_source._message_queue["mark"].qsize())

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_logs_exception_and_reconnects(self, ws_connect_mock, sleep_mock):
        ws_connect_mock.side_effect = [Exception("TEST ERROR"), asyncio.CancelledError()]
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_subscriptions()
        self.assertTrue(self._is_logged(
            "ERROR", "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

    async def test_subscribe_and_unsubscribe_to_trading_pair(self):
        self.assertFalse(await self.data_source.subscribe_to_trading_pair("ETH-USDC"))
        self.assertFalse(await self.data_source.unsubscribe_from_trading_pair("ETH-USDC"))

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair, "ETHUSDC": "ETH-USDC"}))
        ws = MagicMock()
        ws.send = AsyncMock()
        self.data_source._ws_assistant = ws
        self.assertTrue(await self.data_source.subscribe_to_trading_pair("ETH-USDC"))
        self.assertEqual({"op": "subscribe", "args": ["orderbook:ETHUSDC", "trades:ETHUSDC", "mark:ETHUSDC"]},
                         ws.send.call_args.args[0].payload)
        self.assertTrue(await self.data_source.unsubscribe_from_trading_pair("ETH-USDC"))
        self.assertEqual("unsubscribe", ws.send.call_args.args[0].payload["op"])

    # ── parsers ─────────────────────────────────────────────────────────────

    async def test_listen_for_order_book_snapshots_from_websocket(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self._ws_snapshot_event(), asyncio.CancelledError()]
        self.data_source._message_queue["orderbook_snapshot"] = mock_queue
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = 5
        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue))
        msg: OrderBookMessage = await msg_queue.get()

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(self.trading_pair, msg.trading_pair)
        self.assertEqual(77, msg.update_id)
        self.assertEqual(1700000000.0, msg.timestamp)
        self.assertEqual(81500, msg.bids[0].price)
        self.assertEqual(82000, msg.asks[0].price)

    async def test_listen_for_order_book_diffs_successful(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self._ws_diff_event(), asyncio.CancelledError()]
        self.data_source._message_queue["orderbook_delta"] = mock_queue
        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue))
        msg: OrderBookMessage = await msg_queue.get()

        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(78, msg.update_id)
        self.assertEqual(81200, msg.bids[0].price)
        self.assertEqual(0.4, msg.bids[0].amount)
        self.assertEqual(82100, msg.asks[0].price)
        self.assertEqual(0, msg.asks[0].amount)

    async def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue["orderbook_delta"] = mock_queue
        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_diffs(self.local_event_loop, asyncio.Queue())

    async def test_listen_for_order_book_diffs_logs_exception(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [{"topic": f"orderbook:{self.ex_trading_pair}", "type": "delta", "data": {"bids": "bad"}},
                                      asyncio.CancelledError()]
        self.data_source._message_queue["orderbook_delta"] = mock_queue
        try:
            await self.data_source.listen_for_order_book_diffs(self.local_event_loop, asyncio.Queue())
        except asyncio.CancelledError:
            pass
        self.assertTrue(self._is_logged("ERROR", "Unexpected error when processing public order book updates from exchange"))

    async def test_listen_for_trades_successful(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self._ws_trade_event(), asyncio.CancelledError()]
        self.data_source._message_queue["trades"] = mock_queue
        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_trades(self.local_event_loop, msg_queue))
        first: OrderBookMessage = await msg_queue.get()
        second: OrderBookMessage = await msg_queue.get()

        self.assertEqual(OrderBookMessageType.TRADE, first.type)
        self.assertEqual("177396390-1", first.trade_id)
        self.assertEqual(1700000002.0, first.timestamp)
        self.assertEqual(1.0, first.content["trade_type"])
        self.assertEqual("82000", first.content["price"])
        self.assertEqual("177396391-1", second.trade_id)
        self.assertEqual(2.0, second.content["trade_type"])

    async def test_listen_for_trades_logs_exception(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [{"topic": f"trades:{self.ex_trading_pair}", "data": [None]}, asyncio.CancelledError()]
        self.data_source._message_queue["trades"] = mock_queue
        try:
            await self.data_source.listen_for_trades(self.local_event_loop, asyncio.Queue())
        except asyncio.CancelledError:
            pass
        self.assertTrue(self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange"))

    async def test_listen_for_funding_info_from_mark_updates(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self._ws_mark_event(), asyncio.CancelledError()]
        self.data_source._message_queue["mark"] = mock_queue
        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_funding_info(msg_queue))
        update: FundingInfoUpdate = await msg_queue.get()

        self.assertEqual(self.trading_pair, update.trading_pair)
        self.assertEqual(Decimal("82050.5"), update.mark_price)
        self.assertEqual(Decimal("82050.5"), update.index_price)
        self.assertIsNone(update.rate)
        self.assertEqual(Decimal("82050.5"), self.data_source._last_mark_prices[self.trading_pair])

    async def test_listen_for_funding_info_ignores_other_pairs(self):
        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair, "ETHUSDC": "ETH-USDC"}))
        other = self._ws_mark_event()
        other["topic"] = "mark:ETHUSDC"
        other["data"] = {"market": "ETHUSDC", "mark_price": "3000"}
        msg_queue: asyncio.Queue = asyncio.Queue()
        await self.data_source._parse_funding_info_message(other, msg_queue)
        self.assertTrue(msg_queue.empty())
