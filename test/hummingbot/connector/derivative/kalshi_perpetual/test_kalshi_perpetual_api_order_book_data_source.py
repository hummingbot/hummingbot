import asyncio
import base64
import json
from datetime import datetime, timezone
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

import hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_api_order_book_data_source import (
    KalshiPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_auth import KalshiPerpetualAuth
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.web_assistant.connections.data_types import WSResponse


class KalshiPerpetualAPIOrderBookDataSourceTests(IsolatedAsyncioWrapperTestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.trading_pair = "BTC-USD"
        cls.ex_trading_pair = "KXBTCPERP"
        cls.contract_size = Decimal("0.0001")
        cls.api_key = "test-key-id"
        cls.rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        # Generated at runtime: a committed PEM would trip the detect-private-key pre-commit hook.
        cls.private_key_pem = cls.rsa_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

    async def asyncSetUp(self) -> None:
        self.log_records = []
        self.listening_task = None
        self.async_tasks: List[asyncio.Task] = []

        # KalshiPerpetualDerivative is not built yet: the data source only needs the connector for symbol mapping,
        # contract sizes and REST calls, so a mock stands in for it.
        self.connector = MagicMock()
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)
        self.connector.get_contract_size.return_value = self.contract_size
        self.connector._api_get = AsyncMock()

        self.time_provider = MagicMock()
        self.time_provider.time.return_value = 1703123456.789
        self.auth = KalshiPerpetualAuth(
            api_key=self.api_key, private_key=self.private_key_pem, time_provider=self.time_provider)
        self.data_source = KalshiPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=web_utils.build_api_factory(auth=self.auth),
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        for task in self.async_tasks:
            task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    # Fixtures shaped after real Kalshi payloads (REST responses fetched live, WS messages from the AsyncAPI spec)

    def _rest_order_book_response(self) -> Dict[str, Any]:
        # Kalshi returns levels worst-to-best, contrary to its docs; apply_snapshot sorts them anyway.
        return {"orderbook": {"asks": [["7.7822", "662.00"], ["7.7821", "321.00"]],
                              "bids": [["7.7817", "642.00"], ["7.7820", "20.00"]]}}

    def _snapshot_event(self, seq: int = 1, sid: int = 1) -> Dict[str, Any]:
        return {
            "type": "orderbook_snapshot", "sid": sid, "seq": seq,
            "msg": {"market_ticker": self.ex_trading_pair,
                    "bid": [["7.7820", "20.00"], ["7.7817", "642.00"]],
                    "ask": [["7.7821", "321.00"], ["7.7822", "662.00"]]},
        }

    def _delta_event(self, seq: int = 2, price: str = "7.7820", delta: str = "-5.00", side: str = "bid",
                     sid: int = 1) -> Dict[str, Any]:
        return {
            "type": "orderbook_delta", "sid": sid, "seq": seq,
            "msg": {"market_ticker": self.ex_trading_pair, "price": price, "delta": delta, "side": side,
                    "ts_ms": 1789038107243},
        }

    def _trade_event(self, taker_side: str = "bid") -> Dict[str, Any]:
        return {
            "type": "trade", "sid": 2, "seq": 1,
            "msg": {"trade_id": "4c2f7fe4-9bd2-4f6c-9b2b-8c0d3f3a1e55", "market_ticker": self.ex_trading_pair,
                    "price": "7.7825", "count": "3.00", "taker_side": taker_side, "ts_ms": 1789038107000},
        }

    def _ticker_event(self) -> Dict[str, Any]:
        return {
            "type": "ticker", "sid": 3,
            "msg": {"market_ticker": self.ex_trading_pair, "price": "7.7826", "bid": "7.7823", "ask": "7.7825",
                    "reference_price": {"price": "7.7811", "ts_ms": 1789038107000},
                    "settlement_mark_price": {"price": "7.7837", "ts_ms": 1789038103667},
                    "liquidation_mark_price": {"price": "7.7821", "ts_ms": 1789038107243},
                    "funding_rate": {"rate": 0.0001340700855107, "next_funding_time_ms": 1789041600000,
                                     "ts_ms": 1789038108000},
                    "ts_ms": 1789038108000},
        }

    def _subscribed_events(self) -> List[Dict[str, Any]]:
        return [{"id": 1, "type": "subscribed", "msg": {"channel": channel, "sid": sid}}
                for sid, channel in enumerate(["orderbook_delta", "trade", "ticker"], start=1)]

    def _ws_assistant_yielding(self, messages: List[Dict[str, Any]]) -> MagicMock:
        async def iter_messages():
            for message in messages:
                yield WSResponse(data=message)

        ws_assistant = MagicMock()
        ws_assistant.iter_messages = iter_messages
        return ws_assistant

    async def _processed(self, messages: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Runs raw messages through the websocket read loop and returns what each queue received."""
        await self.data_source._process_websocket_messages(self._ws_assistant_yielding(messages))
        queued = {}
        for key in self.data_source._get_messages_queue_keys():
            queue = self.data_source._message_queue[key]
            queued[key] = [queue.get_nowait() for _ in range(queue.qsize())]
        return queued

    # REST — order book

    async def test_get_new_order_book_successful(self):
        self.connector._api_get.return_value = self._rest_order_book_response()

        order_book = await self.data_source.get_new_order_book(self.trading_pair)

        self.connector._api_get.assert_awaited_once_with(
            path_url="/margin/markets/KXBTCPERP/orderbook", limit_id=CONSTANTS.ORDER_BOOK_PATH_URL)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        # Per-contract prices and contract counts converted to USD/BTC and BTC with the 0.0001 BTC contract size
        self.assertEqual([(77820.0, 0.002), (77817.0, 0.0642)], [(row.price, row.amount) for row in bids])
        self.assertEqual([(77821.0, 0.0321), (77822.0, 0.0662)], [(row.price, row.amount) for row in asks])
        self.assertEqual(1, order_book.snapshot_uid)

    async def test_get_new_order_book_raises_exception(self):
        self.connector._api_get.side_effect = IOError("HTTP status is 500")

        with self.assertRaises(IOError):
            await self.data_source.get_new_order_book(self.trading_pair)

    # REST — funding info

    async def test_get_funding_info(self):
        market_response = {"market": {"ticker": self.ex_trading_pair,
                                      "reference_price": {"price": "7.7811", "ts_ms": 1789038107000}}}
        funding_estimate = {"computed_time": "2026-09-10T11:01:48.66841Z", "funding_rate": 0.0001340700855107,
                            "mark_price": "7.7837", "market_ticker": self.ex_trading_pair,
                            "next_funding_time": "2026-09-10T12:00:00Z"}
        self.connector._api_get.side_effect = lambda path_url, **_: (
            market_response if path_url == "/margin/markets/KXBTCPERP" else funding_estimate)

        funding_info = await self.data_source.get_funding_info(self.trading_pair)

        self.assertIsInstance(funding_info, FundingInfo)
        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal("77811"), funding_info.index_price)
        self.assertEqual(Decimal("77837"), funding_info.mark_price)
        self.assertEqual(int(datetime(2026, 9, 10, 12, tzinfo=timezone.utc).timestamp()),
                         funding_info.next_funding_utc_timestamp)
        self.assertEqual(Decimal("0.0001340700855107"), funding_info.rate)
        self.connector._api_get.assert_any_await(
            path_url=CONSTANTS.FUNDING_RATE_ESTIMATE_PATH_URL, params={"ticker": self.ex_trading_pair},
            limit_id=CONSTANTS.FUNDING_RATE_ESTIMATE_PATH_URL)

    # WEBSOCKET — listen_for_subscriptions

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs_and_funding_info(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        for event in self._subscribed_events():
            self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(event))

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        # Signed handshake on the margin WS URL
        self.assertEqual(CONSTANTS.WSS_URLS[CONSTANTS.DEFAULT_DOMAIN], ws_connect_mock.call_args.args[0])
        self.assertEqual(CONSTANTS.HEARTBEAT_TIME_INTERVAL, ws_connect_mock.call_args.kwargs["heartbeat"])
        headers = ws_connect_mock.call_args.kwargs["headers"]
        self.assertEqual(self.api_key, headers["KALSHI-ACCESS-KEY"])
        self.assertEqual("1703123456789", headers["KALSHI-ACCESS-TIMESTAMP"])
        self.rsa_key.public_key().verify(
            base64.b64decode(headers["KALSHI-ACCESS-SIGNATURE"]),
            b"1703123456789GET/trade-api/ws/v2/margin",
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)
        self.assertEqual(1, len(sent_messages))
        self.assertEqual(
            {"id": 1, "cmd": "subscribe",
             "params": {"channels": ["orderbook_delta", "trade", "ticker"], "market_tickers": [self.ex_trading_pair]}},
            sent_messages[0],
        )
        self.assertEqual({"orderbook_delta": 1, "trade": 2, "ticker": 3}, self.data_source._channel_sids)
        self.assertTrue(self._is_logged("INFO", "Subscribed to public order book, trade and ticker channels..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_raises_cancel_exception(self, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_subscriptions()

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_logs_exception_details(self, ws_connect_mock, sleep_mock):
        sleep_mock.side_effect = asyncio.CancelledError
        ws_connect_mock.side_effect = Exception("TEST ERROR.")

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_subscriptions()

        self.assertTrue(self._is_logged(
            "ERROR", "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

    async def test_connected_websocket_assistant_requires_credentials(self):
        data_source = KalshiPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair], connector=self.connector, api_factory=web_utils.build_api_factory())

        with self.assertRaises(ValueError):
            await data_source._connected_websocket_assistant()

    async def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._subscribe_channels(mock_ws)

    async def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            await self.data_source._subscribe_channels(mock_ws)

        self.assertTrue(self._is_logged("ERROR", "Unexpected error occurred subscribing to order book streams..."))

    def test_channel_originating_message(self):
        self.assertEqual(self.data_source._snapshot_messages_queue_key,
                         self.data_source._channel_originating_message(self._snapshot_event()))
        self.assertEqual(self.data_source._diff_messages_queue_key,
                         self.data_source._channel_originating_message(self._delta_event()))
        self.assertEqual(self.data_source._trade_messages_queue_key,
                         self.data_source._channel_originating_message(self._trade_event()))
        self.assertEqual(self.data_source._funding_info_messages_queue_key,
                         self.data_source._channel_originating_message(self._ticker_event()))
        self.assertNotIn(self.data_source._channel_originating_message(self._subscribed_events()[0]),
                         self.data_source._get_messages_queue_keys())

    async def test_process_websocket_messages_tracks_book_and_converts_deltas_to_sizes(self):
        queued = await self._processed([
            self._snapshot_event(seq=1),
            self._delta_event(seq=2, price="7.7820", delta="-5.00"),   # 20 -> 15
            self._delta_event(seq=3, price="7.7817", delta="-642.00"),  # level removed
            self._delta_event(seq=4, price="7.7819", delta="7.00"),     # new level
        ])

        snapshot, = queued[self.data_source._snapshot_messages_queue_key]
        deltas = queued[self.data_source._diff_messages_queue_key]
        self.assertEqual(1, snapshot["update_id"])
        self.assertEqual([2, 3, 4], [delta["update_id"] for delta in deltas])
        self.assertEqual([Decimal("15"), Decimal("0"), Decimal("7")], [delta["size"] for delta in deltas])
        self.assertEqual({Decimal("7.7820"): Decimal("15"), Decimal("7.7819"): Decimal("7")},
                         self.data_source._local_books[self.ex_trading_pair]["bid"])

    async def test_process_websocket_messages_sequence_gap_raises_connection_error(self):
        with self.assertRaises(ConnectionError) as context:
            await self._processed([self._snapshot_event(seq=1), self._delta_event(seq=3)])

        self.assertEqual("Order book sequence gap on subscription 1 (expected seq 2, got 3)", str(context.exception))

    async def test_update_ids_keep_increasing_across_reconnections_and_rest_snapshots(self):
        await self._processed([self._snapshot_event(seq=1), self._delta_event(seq=2)])
        await self.data_source._subscribe_channels(AsyncMock())  # reconnection: Kalshi restarts seq at 1
        self.connector._api_get.return_value = self._rest_order_book_response()
        rest_snapshot = await self.data_source._order_book_snapshot(self.trading_pair)

        queued = await self._processed([self._snapshot_event(seq=1)])

        self.assertEqual(3, rest_snapshot.update_id)
        self.assertEqual(4, queued[self.data_source._snapshot_messages_queue_key][0]["update_id"])

    async def test_process_websocket_messages_records_sids(self):
        await self._processed(self._subscribed_events())

        self.assertEqual({"orderbook_delta": 1, "trade": 2, "ticker": 3}, self.data_source._channel_sids)

    async def test_error_message_raises_to_reconnect_after_a_pause(self):
        # A rejected subscription keeps the connection open without its streams
        error_event = {"id": 1, "type": "error", "msg": {"code": 9, "msg": "Authentication required"}}

        with self.assertRaises(IOError) as context:
            await self._processed([*self._subscribed_events(), error_event])

        # A ConnectionError would reconnect without pausing, in a loop if the error persists
        self.assertNotIsInstance(context.exception, ConnectionError)
        self.assertEqual(
            "Kalshi order book stream error: {'code': 9, 'msg': 'Authentication required'}", str(context.exception))

    # WEBSOCKET — listen_for_trades

    async def test_listen_for_trades_successful(self):
        msg_queue: asyncio.Queue = asyncio.Queue()
        self.data_source._message_queue[self.data_source._trade_messages_queue_key].put_nowait(self._trade_event())

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_trades(self.local_event_loop, msg_queue))
        trade_message: OrderBookMessage = await msg_queue.get()

        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(self.trading_pair, trade_message.trading_pair)
        self.assertEqual("4c2f7fe4-9bd2-4f6c-9b2b-8c0d3f3a1e55", trade_message.trade_id)
        self.assertEqual(float(TradeType.BUY.value), trade_message.content["trade_type"])
        self.assertEqual(Decimal("77825"), trade_message.content["price"])
        self.assertEqual(Decimal("0.0003"), trade_message.content["amount"])
        self.assertEqual(1789038107.0, trade_message.timestamp)

    async def test_listen_for_trades_taker_ask_is_a_sell(self):
        msg_queue: asyncio.Queue = asyncio.Queue()

        await self.data_source._parse_trade_message(self._trade_event(taker_side="ask"), msg_queue)

        self.assertEqual(float(TradeType.SELL.value), msg_queue.get_nowait().content["trade_type"])

    async def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_trades(self.local_event_loop, asyncio.Queue())

    async def test_listen_for_trades_logs_exception(self):
        incomplete_event = {"type": "trade", "sid": 2, "seq": 1, "msg": {"market_ticker": self.ex_trading_pair}}
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_trades(self.local_event_loop, asyncio.Queue())

        self.assertTrue(self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange"))

    # WEBSOCKET — listen_for_order_book_diffs

    async def test_listen_for_order_book_diffs_successful(self):
        msg_queue: asyncio.Queue = asyncio.Queue()
        await self._processed([self._snapshot_event(seq=1)])
        await self.data_source._process_websocket_messages(
            self._ws_assistant_yielding([self._delta_event(seq=2, price="7.7820", delta="-5.00", side="bid")]))

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue))
        diff_message: OrderBookMessage = await msg_queue.get()

        self.assertEqual(OrderBookMessageType.DIFF, diff_message.type)
        self.assertEqual(self.trading_pair, diff_message.trading_pair)
        self.assertEqual(2, diff_message.update_id)
        self.assertEqual([(77820.0, 0.0015)], [(row.price, row.amount) for row in diff_message.bids])
        self.assertEqual([], diff_message.asks)
        self.assertEqual(1789038107.243, diff_message.timestamp)

    async def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_diffs(self.local_event_loop, asyncio.Queue())

    async def test_listen_for_order_book_diffs_logs_exception(self):
        mock_queue = AsyncMock()
        # A delta that never went through the read loop has no size/update_id, so parsing fails
        mock_queue.get.side_effect = [self._delta_event(), asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_diffs(self.local_event_loop, asyncio.Queue())

        self.assertTrue(self._is_logged(
            "ERROR", "Unexpected error when processing public order book updates from exchange"))

    # WEBSOCKET — listen_for_order_book_snapshots

    async def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self):
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = 0  # no WS snapshot queued -> REST snapshot
        self.connector._api_get.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_snapshots(self.local_event_loop, asyncio.Queue())

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    async def test_listen_for_order_book_snapshots_log_exception(self, sleep_mock):
        sleep_mock.side_effect = asyncio.CancelledError
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = 0
        self.connector._api_get.side_effect = Exception("TEST ERROR")

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_snapshots(self.local_event_loop, asyncio.Queue())

        self.assertTrue(self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}."))
        self.assertTrue(self._is_logged(
            "ERROR", "Unexpected error when processing public order book snapshots from exchange"))

    async def test_listen_for_order_book_snapshots_successful(self):
        msg_queue: asyncio.Queue = asyncio.Queue()
        await self._processed([self._snapshot_event(seq=1)])
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key].put_nowait(
            {**self._snapshot_event(seq=1), "update_id": 1})

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.local_event_loop, msg_queue))
        snapshot_message: OrderBookMessage = await msg_queue.get()

        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(self.trading_pair, snapshot_message.trading_pair)
        self.assertEqual(1, snapshot_message.update_id)
        self.assertEqual([(77820.0, 0.002), (77817.0, 0.0642)],
                         [(row.price, row.amount) for row in snapshot_message.bids])
        self.assertEqual([(77821.0, 0.0321), (77822.0, 0.0662)],
                         [(row.price, row.amount) for row in snapshot_message.asks])

    # WEBSOCKET — listen_for_funding_info

    async def test_listen_for_funding_info_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._funding_info_messages_queue_key] = mock_queue

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_funding_info(asyncio.Queue())

    async def test_listen_for_funding_info_logs_exception(self):
        broken_ticker = {
            "type": "ticker", "sid": 3,
            "msg": {"market_ticker": self.ex_trading_pair, "reference_price": {"ts_ms": 1789038107000}},
        }
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [broken_ticker, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._funding_info_messages_queue_key] = mock_queue

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_funding_info(asyncio.Queue())

        self.assertTrue(self._is_logged(
            "ERROR", "Unexpected error when processing public funding info updates from exchange"))

    async def test_listen_for_funding_info_successful(self):
        msg_queue: asyncio.Queue = asyncio.Queue()
        self.data_source._message_queue[self.data_source._funding_info_messages_queue_key].put_nowait(
            self._ticker_event())

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_funding_info(msg_queue))
        funding_update: FundingInfoUpdate = await msg_queue.get()

        self.assertEqual(self.trading_pair, funding_update.trading_pair)
        self.assertEqual(Decimal("77811"), funding_update.index_price)
        self.assertEqual(Decimal("77837"), funding_update.mark_price)
        self.assertEqual(1789041600, funding_update.next_funding_utc_timestamp)
        self.assertEqual(Decimal("0.0001340700855107"), funding_update.rate)

    async def test_parse_funding_info_message_partial_ticker_only_updates_present_fields(self):
        msg_queue: asyncio.Queue = asyncio.Queue()
        ticker = self._ticker_event()
        del ticker["msg"]["funding_rate"], ticker["msg"]["reference_price"]

        await self.data_source._parse_funding_info_message(ticker, msg_queue)

        funding_update: FundingInfoUpdate = msg_queue.get_nowait()
        self.assertEqual(Decimal("77837"), funding_update.mark_price)
        self.assertIsNone(funding_update.index_price)
        self.assertIsNone(funding_update.rate)
        self.assertIsNone(funding_update.next_funding_utc_timestamp)

    async def test_parse_funding_info_message_ignores_tickers_without_funding_fields(self):
        msg_queue: asyncio.Queue = asyncio.Queue()
        ticker = self._ticker_event()
        for field in ("funding_rate", "reference_price", "settlement_mark_price"):
            del ticker["msg"][field]

        await self.data_source._parse_funding_info_message(ticker, msg_queue)

        self.assertTrue(msg_queue.empty())

    # Dynamic subscriptions (update_subscription)

    async def test_subscribe_to_trading_pair_successful(self):
        self.data_source._ws_assistant = AsyncMock()
        self.data_source._channel_sids = {"orderbook_delta": 1, "trade": 2, "ticker": 3}
        self.connector.exchange_symbol_associated_to_pair.return_value = "KXETHPERP"

        result = await self.data_source.subscribe_to_trading_pair("ETH-USD")

        self.assertTrue(result)
        sent_request = self.data_source._ws_assistant.send.call_args.args[0]
        self.assertEqual(
            {"id": 1, "cmd": "update_subscription",
             "params": {"sids": [1, 2, 3], "market_tickers": ["KXETHPERP"], "action": "add_markets"}},
            sent_request.payload,
        )
        self.assertIn("ETH-USD", self.data_source._trading_pairs)
        self.assertTrue(self._is_logged("INFO", "Requested to subscribe to ETH-USD order book, trade and ticker channels"))

    async def test_subscribe_to_trading_pair_websocket_not_connected(self):
        result = await self.data_source.subscribe_to_trading_pair("ETH-USD")

        self.assertFalse(result)
        self.assertTrue(self._is_logged("WARNING", "Cannot subscribe to ETH-USD: WebSocket not connected"))

    async def test_subscribe_to_trading_pair_raises_exception_and_logs_error(self):
        self.data_source._ws_assistant = AsyncMock()
        self.data_source._ws_assistant.send.side_effect = Exception("Test Error")
        self.data_source._channel_sids = {"orderbook_delta": 1, "trade": 2, "ticker": 3}

        result = await self.data_source.subscribe_to_trading_pair("ETH-USD")

        self.assertFalse(result)
        self.assertTrue(self._is_logged("ERROR", "Error trying to subscribe to ETH-USD"))

    async def test_unsubscribe_from_trading_pair_successful(self):
        self.data_source._ws_assistant = AsyncMock()
        self.data_source._channel_sids = {"orderbook_delta": 1, "trade": 2, "ticker": 3}
        await self._processed([self._snapshot_event(seq=1)])

        result = await self.data_source.unsubscribe_from_trading_pair(self.trading_pair)

        self.assertTrue(result)
        self.assertEqual("delete_markets", self.data_source._ws_assistant.send.call_args.args[0].payload["params"]["action"])
        self.assertNotIn(self.trading_pair, self.data_source._trading_pairs)
        self.assertNotIn(self.ex_trading_pair, self.data_source._local_books)

    async def test_get_last_traded_prices_delegates_to_connector(self):
        self.connector.get_last_traded_prices = AsyncMock(return_value={self.trading_pair: 77826.0})

        result = await self.data_source.get_last_traded_prices([self.trading_pair])

        self.assertEqual({self.trading_pair: 77826.0}, result)
