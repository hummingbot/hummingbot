import asyncio
from decimal import Decimal
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

from hummingbot.connector.exchange.gemini import gemini_constants as CONSTANTS
from hummingbot.connector.exchange.gemini.gemini_exchange import (
    GeminiExchange,
    GeminiWSAmbiguousResponseError,
    GeminiWSRejectionError,
    GeminiWSTransportError,
)
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee
from hummingbot.core.web_assistant.connections.data_types import WSResponse


class _FakeTradeWS:
    """Minimal stand-in for a WSAssistant that yields canned messages."""

    def __init__(self, messages):
        self._messages = messages
        self.disconnected = False

    async def iter_messages(self):
        for message in self._messages:
            yield message

    async def disconnect(self):
        self.disconnected = True


class _ScriptedWSAssistant:
    """Fake WSAssistant that acks every sent request, for driving the real
    _connected_trade_ws -> _trade_ws_listener -> pending-future plumbing."""

    def __init__(self, result=None):
        self.connect_calls = []
        self.sent_payloads = []
        self.disconnected = False
        self._queue = None
        self._result = {"orderId": 4242} if result is None else result

    async def connect(self, ws_url, ping_timeout=None, ws_headers=None, **kwargs):
        self.connect_calls.append({"ws_url": ws_url, "ws_headers": ws_headers})
        self._queue = asyncio.Queue()

    async def send(self, request):
        self.sent_payloads.append(request.payload)
        await self._queue.put(WSResponse(data={
            "id": request.payload["id"], "status": 200, "result": dict(self._result)}))

    async def iter_messages(self):
        while not self.disconnected:
            message = await self._queue.get()
            if message is None:
                return
            yield message

    async def disconnect(self):
        self.disconnected = True
        if self._queue is not None:
            await self._queue.put(None)


class GeminiExchangeTests(TestCase):

    def setUp(self):
        self.exchange = GeminiExchange(
            gemini_api_key="test_key",
            gemini_api_secret="test_secret",
            trading_pairs=["BTC-USD", "ETH-USD"],
            trading_required=False,
        )

    def test_name(self):
        self.assertEqual("gemini", self.exchange.name)

    def test_supported_order_types(self):
        order_types = self.exchange.supported_order_types()
        self.assertIn(OrderType.LIMIT, order_types)
        self.assertIn(OrderType.LIMIT_MAKER, order_types)

    def test_trading_pairs(self):
        self.assertEqual(["BTC-USD", "ETH-USD"], self.exchange.trading_pairs)

    def test_is_cancel_request_in_exchange_synchronous(self):
        self.assertTrue(self.exchange.is_cancel_request_in_exchange_synchronous)

    def test_split_gemini_symbol(self):
        self.assertEqual(("btc", "usd"), GeminiExchange._split_gemini_symbol("btcusd"))
        self.assertEqual(("eth", "usd"), GeminiExchange._split_gemini_symbol("ethusd"))
        self.assertEqual(("btc", "gusd"), GeminiExchange._split_gemini_symbol("btcgusd"))
        self.assertEqual(("eth", "btc"), GeminiExchange._split_gemini_symbol("ethbtc"))
        self.assertEqual(("sol", "usdt"), GeminiExchange._split_gemini_symbol("solusdt"))
        self.assertEqual(("", ""), GeminiExchange._split_gemini_symbol("x"))
        self.assertEqual(("matic", "usd"), GeminiExchange._split_gemini_symbol("maticusd"))

    def test_client_order_id_prefix(self):
        self.assertEqual("HBOT", self.exchange.client_order_id_prefix)

    def test_client_order_id_max_length(self):
        self.assertEqual(36, self.exchange.client_order_id_max_length)

    # ------------------------------------------------------------------
    # P0-2: LIMIT_MAKER must be classified as a maker order
    # ------------------------------------------------------------------

    def test_get_fee_limit_maker_uses_maker_fee(self):
        fee = self.exchange._get_fee(
            base_currency="BTC",
            quote_currency="USD",
            order_type=OrderType.LIMIT_MAKER,
            order_side=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
        )
        self.assertIsInstance(fee, DeductedFromReturnsTradeFee)
        # Default Gemini schema: maker = 0.002, taker = 0.004
        self.assertEqual(Decimal("0.002"), fee.percent)

    def test_get_fee_limit_uses_maker_fee(self):
        fee = self.exchange._get_fee(
            base_currency="BTC",
            quote_currency="USD",
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
        )
        self.assertEqual(Decimal("0.002"), fee.percent)

    def test_get_fee_explicit_is_maker_false_uses_taker(self):
        fee = self.exchange._get_fee(
            base_currency="BTC",
            quote_currency="USD",
            order_type=OrderType.LIMIT_MAKER,
            order_side=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
            is_maker=False,
        )
        self.assertEqual(Decimal("0.004"), fee.percent)

    # ------------------------------------------------------------------
    # P0-1 helpers + tests: WS Z field is cumulative, must convert to delta
    # ------------------------------------------------------------------

    @staticmethod
    def _async_run(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _start_tracking_limit_buy(self, order_id="HBOT1", exchange_order_id="100234",
                                  trading_pair="BTC-USD", price="100", amount="1",
                                  order_type=OrderType.LIMIT):
        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=TradeType.BUY,
            price=Decimal(price),
            amount=Decimal(amount),
        )
        return self.exchange.in_flight_orders[order_id]

    @staticmethod
    def _make_fill_event(client_order_id, exchange_order_id, status,
                         cumulative_z, last_price, trade_id,
                         event_ts_ns=1_700_000_000_000_000_000):
        return {
            "e": "executionReport",
            "E": event_ts_ns,
            "s": "BTCUSD",
            "i": exchange_order_id,
            "c": client_order_id,
            "S": "BUY",
            "o": "LIMIT",
            "X": status,
            "p": "100",
            "q": "1",
            "z": str(cumulative_z),
            "Z": str(cumulative_z),
            "L": str(last_price),
            "t": trade_id,
            "T": event_ts_ns,
        }

    def _drive_user_stream(self, events):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = list(events) + [asyncio.CancelledError]
        # _user_stream_tracker is created lazily on first access
        self.exchange._user_stream_tracker._user_stream = mock_queue
        try:
            self._async_run(
                asyncio.wait_for(self.exchange._user_stream_event_listener(), timeout=2)
            )
        except asyncio.CancelledError:
            pass

    def test_user_stream_partial_fill_uses_delta(self):
        order = self._start_tracking_limit_buy(amount="1")

        partial = self._make_fill_event(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            status="PARTIALLY_FILLED",
            cumulative_z="0.3",
            last_price="100",
            trade_id="trade-1",
        )
        full = self._make_fill_event(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            status="FILLED",
            cumulative_z="1.0",
            last_price="101",
            trade_id="trade-2",
        )

        self._drive_user_stream([partial, full])

        # The InFlightOrder reference is the same object the tracker mutates,
        # whether or not the order is still in `in_flight_orders` after FILLED.
        self.assertEqual(Decimal("1.0"), order.executed_amount_base)
        self.assertEqual(2, len(order.order_fills))

        first_fill = order.order_fills["trade-1"]
        second_fill = order.order_fills["trade-2"]
        self.assertEqual(Decimal("0.3"), first_fill.fill_base_amount)
        self.assertEqual(Decimal("100"), first_fill.fill_price)
        self.assertEqual(Decimal("0.7"), second_fill.fill_base_amount)
        self.assertEqual(Decimal("101"), second_fill.fill_price)

    def test_user_stream_duplicate_fill_event_ignored(self):
        order = self._start_tracking_limit_buy(amount="1")

        first = self._make_fill_event(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            status="PARTIALLY_FILLED",
            cumulative_z="0.5",
            last_price="100",
            trade_id="trade-1",
        )
        # Same trade id replayed (e.g. WS reconnect or duplicate delivery)
        duplicate = self._make_fill_event(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            status="PARTIALLY_FILLED",
            cumulative_z="0.5",
            last_price="100",
            trade_id="trade-1",
        )

        self._drive_user_stream([first, duplicate])

        self.assertEqual(Decimal("0.5"), order.executed_amount_base)
        self.assertEqual(1, len(order.order_fills))
        self.assertIn("trade-1", order.order_fills)

    def test_user_stream_fill_event_without_trade_id_is_skipped(self):
        order = self._start_tracking_limit_buy(amount="1")

        event = self._make_fill_event(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            status="PARTIALLY_FILLED",
            cumulative_z="0.5",
            last_price="100",
            trade_id="trade-1",
        )
        event.pop("t")  # missing trade id — must not record a fill

        self._drive_user_stream([event])

        self.assertEqual(Decimal("0"), order.executed_amount_base)
        self.assertEqual(0, len(order.order_fills))

    # ------------------------------------------------------------------
    # Misc property / predicate coverage
    # ------------------------------------------------------------------

    def test_simple_properties(self):
        self.assertEqual("", self.exchange.domain)
        self.assertEqual(CONSTANTS.RATE_LIMITS, self.exchange.rate_limits_rules)
        self.assertEqual(CONSTANTS.SYMBOLS_PATH_URL, self.exchange.trading_rules_request_path)
        self.assertEqual(CONSTANTS.SYMBOLS_PATH_URL, self.exchange.trading_pairs_request_path)
        self.assertEqual(CONSTANTS.SYMBOLS_PATH_URL, self.exchange.check_network_request_path)
        self.assertFalse(self.exchange.is_trading_required)

    def test_authenticator_is_gemini_auth(self):
        from hummingbot.connector.exchange.gemini.gemini_auth import GeminiAuth
        self.assertIsInstance(self.exchange.authenticator, GeminiAuth)

    def test_get_all_pairs_prices_returns_empty(self):
        self.assertEqual([], self._async_run(self.exchange.get_all_pairs_prices()))

    def test_is_request_exception_related_to_time_synchronizer(self):
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(
            Exception("InvalidNonce: bad")))
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(
            Exception("nonce not within 30 seconds")))
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(
            Exception("some other error")))

    def test_order_not_found_predicates(self):
        not_found = Exception(CONSTANTS.ORDER_NOT_FOUND_ERROR)
        other = Exception("boom")
        self.assertTrue(self.exchange._is_order_not_found_during_status_update_error(not_found))
        self.assertFalse(self.exchange._is_order_not_found_during_status_update_error(other))
        self.assertTrue(self.exchange._is_order_not_found_during_cancelation_error(not_found))
        self.assertFalse(self.exchange._is_order_not_found_during_cancelation_error(other))

    def test_update_trading_fees_is_noop(self):
        self.assertIsNone(self._async_run(self.exchange._update_trading_fees()))

    @patch.object(ExchangePyBase, "_status_polling_loop_fetch_updates", new_callable=AsyncMock)
    def test_status_polling_loop_fetch_updates_delegates(self, super_mock):
        self._async_run(self.exchange._status_polling_loop_fetch_updates())
        super_mock.assert_awaited_once()

    @patch.object(ExchangePyBase, "_update_time_synchronizer", new_callable=AsyncMock)
    def test_update_time_synchronizer_clears_samples(self, super_mock):
        self.exchange._time_synchronizer.clear_time_offset_ms_samples = lambda: setattr(self, "_cleared", True)
        self._async_run(self.exchange._update_time_synchronizer())
        self.assertTrue(getattr(self, "_cleared", False))
        super_mock.assert_awaited_once()

    # ------------------------------------------------------------------
    # Trading pair symbol map
    # ------------------------------------------------------------------

    def _set_symbol_map(self):
        self.exchange._set_trading_pair_symbol_map(bidict({"btcusd": "BTC-USD", "ethusd": "ETH-USD"}))

    def test_initialize_trading_pair_symbols_from_exchange_info(self):
        self.exchange._initialize_trading_pair_symbols_from_exchange_info(["btcusd", "ethusd", "x"])
        symbol_map = self._async_run(self.exchange.trading_pair_symbol_map())
        self.assertEqual("BTC-USD", symbol_map["btcusd"])
        self.assertEqual("ETH-USD", symbol_map["ethusd"])
        self.assertNotIn("x", symbol_map)

    # ------------------------------------------------------------------
    # Order placement — websocket-first
    # ------------------------------------------------------------------

    def test_place_order_ws_success(self):
        self._set_symbol_map()
        self.exchange._trade_ws_request = AsyncMock(
            return_value={"id": "1", "status": 200, "result": {"orderId": 9876}})
        self.exchange._api_post = AsyncMock()

        o_id, ts = self._async_run(self.exchange._place_order(
            order_id="HBOT1", trading_pair="BTC-USD", amount=Decimal("1"),
            trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("100")))

        self.assertEqual("9876", o_id)
        self.assertGreater(ts, 0)
        self.exchange._api_post.assert_not_called()
        _, kwargs = self.exchange._trade_ws_request.call_args
        self.assertEqual(CONSTANTS.WS_METHOD_ORDER_PLACE, kwargs["method"])
        self.assertEqual(CONSTANTS.WS_ORDER_PLACE_LIMIT_ID, kwargs["throttler_limit_id"])
        params = kwargs["params"]
        self.assertEqual("btcusd", params["symbol"])
        self.assertEqual(CONSTANTS.WS_SIDE_BUY, params["side"])
        self.assertEqual(CONSTANTS.WS_ORDER_TYPE_LIMIT, params["type"])
        self.assertEqual(CONSTANTS.WS_TIME_IN_FORCE_GTC, params["timeInForce"])
        self.assertEqual("100", params["price"])
        self.assertEqual("1", params["quantity"])
        self.assertEqual("HBOT1", params["clientOrderId"])

    def test_place_order_ws_limit_maker_uses_moc(self):
        self._set_symbol_map()
        self.exchange._trade_ws_request = AsyncMock(
            return_value={"id": "1", "status": 200, "result": {"orderId": 1}})

        self._async_run(self.exchange._place_order(
            order_id="HBOT1", trading_pair="ETH-USD", amount=Decimal("1"),
            trade_type=TradeType.SELL, order_type=OrderType.LIMIT_MAKER, price=Decimal("100")))

        _, kwargs = self.exchange._trade_ws_request.call_args
        params = kwargs["params"]
        self.assertEqual(CONSTANTS.WS_SIDE_SELL, params["side"])
        self.assertEqual(CONSTANTS.WS_TIME_IN_FORCE_MOC, params["timeInForce"])

    def test_place_order_ws_ack_without_id_uses_tracked_order(self):
        self._set_symbol_map()
        self._start_tracking_limit_buy(order_id="HBOT1", exchange_order_id="777")
        self.exchange._trade_ws_request = AsyncMock(
            return_value={"id": "1", "status": 200, "result": {}})

        o_id, _ = self._async_run(self.exchange._place_order(
            order_id="HBOT1", trading_pair="BTC-USD", amount=Decimal("1"),
            trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("100")))

        self.assertEqual("777", o_id)

    def test_place_order_ws_ack_without_id_waits_for_user_stream_event(self):
        # In production the order is tracked with exchange_order_id=None before
        # placement; the id arrives later via the orders@account NEW event.
        self._set_symbol_map()
        self.exchange.start_tracking_order(
            order_id="HBOT1", exchange_order_id=None, trading_pair="BTC-USD",
            order_type=OrderType.LIMIT, trade_type=TradeType.BUY,
            price=Decimal("100"), amount=Decimal("1"))
        order = self.exchange.in_flight_orders["HBOT1"]
        self.exchange._trade_ws_request = AsyncMock(
            return_value={"id": "1", "status": 200, "result": {}})
        self.exchange._api_post = AsyncMock()

        async def scenario():
            async def deliver_new_event():
                await asyncio.sleep(0.05)
                order.update_exchange_order_id("777")

            delivery_task = asyncio.get_running_loop().create_task(deliver_new_event())
            placement = await self.exchange._place_order(
                order_id="HBOT1", trading_pair="BTC-USD", amount=Decimal("1"),
                trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("100"))
            await delivery_task
            return placement

        o_id, _ = self._async_run(scenario())

        self.assertEqual("777", o_id)
        self.exchange._api_post.assert_not_called()

    def test_place_order_ws_ack_without_id_timeout_reconciles_via_rest(self):
        self._set_symbol_map()
        self.exchange.start_tracking_order(
            order_id="HBOT1", exchange_order_id=None, trading_pair="BTC-USD",
            order_type=OrderType.LIMIT, trade_type=TradeType.BUY,
            price=Decimal("100"), amount=Decimal("1"))
        self.exchange._trade_ws_request = AsyncMock(
            return_value={"id": "1", "status": 200, "result": {}})
        self.exchange._api_post = AsyncMock(
            return_value={"order_id": 888, "timestampms": 1700000000000, "is_live": True})

        with patch("hummingbot.core.data_type.in_flight_order.GET_EX_ORDER_ID_TIMEOUT", 0.05):
            o_id, _ = self._async_run(self.exchange._place_order(
                order_id="HBOT1", trading_pair="BTC-USD", amount=Decimal("1"),
                trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("100")))

        self.assertEqual("888", o_id)
        # REST was used once, for the status reconcile — never for a second placement
        self.exchange._api_post.assert_awaited_once()
        _, kwargs = self.exchange._api_post.call_args
        self.assertEqual(CONSTANTS.ORDER_STATUS_PATH_URL, kwargs["path_url"])
        self.assertEqual("HBOT1", kwargs["data"]["client_order_id"])

    def test_place_order_ws_ack_without_order_event_places_via_rest(self):
        # Per Gemini: an order.place ack is not proof of placement. No order event
        # arriving AND REST reporting no such order means "not placed" — the
        # placement must fall through to REST instead of failing the order.
        self._set_symbol_map()
        self.exchange.start_tracking_order(
            order_id="HBOT1", exchange_order_id=None, trading_pair="BTC-USD",
            order_type=OrderType.LIMIT, trade_type=TradeType.BUY,
            price=Decimal("100"), amount=Decimal("1"))
        self.exchange._trade_ws_request = AsyncMock(
            return_value={"id": "1", "status": 200, "result": {}})
        self.exchange._api_post = AsyncMock(side_effect=[
            IOError("OrderNotFound: no such order"),
            {"order_id": 9876, "timestampms": 1700000000000},
        ])

        with patch("hummingbot.core.data_type.in_flight_order.GET_EX_ORDER_ID_TIMEOUT", 0.05):
            o_id, _ = self._async_run(self.exchange._place_order(
                order_id="HBOT1", trading_pair="BTC-USD", amount=Decimal("1"),
                trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("100")))

        self.assertEqual("9876", o_id)
        self.assertEqual(2, self.exchange._api_post.await_count)
        _, placement_kwargs = self.exchange._api_post.call_args
        self.assertEqual(CONSTANTS.NEW_ORDER_PATH_URL, placement_kwargs["path_url"])

    def test_place_order_ws_ack_untracked_and_not_found_places_via_rest(self):
        self._set_symbol_map()
        self.exchange._trade_ws_request = AsyncMock(
            return_value={"id": "1", "status": 200, "result": None})
        self.exchange._api_post = AsyncMock(side_effect=[
            IOError("OrderNotFound"),
            {"order_id": 9876, "timestampms": 1700000000000},
        ])

        o_id, _ = self._async_run(self.exchange._place_order(
            order_id="HBOT-untracked", trading_pair="BTC-USD", amount=Decimal("1"),
            trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("100")))

        self.assertEqual("9876", o_id)
        self.assertEqual(2, self.exchange._api_post.await_count)

    def test_place_order_ws_rejection_does_not_fall_back_to_rest(self):
        self._set_symbol_map()
        self.exchange._trade_ws_request = AsyncMock(return_value={
            "id": "1", "status": 400,
            "error": {"code": -2010, "msg": "Order rejected - insufficient funds"}})
        self.exchange._api_post = AsyncMock()

        with self.assertRaises(GeminiWSRejectionError):
            self._async_run(self.exchange._place_order(
                order_id="HBOT1", trading_pair="BTC-USD", amount=Decimal("1"),
                trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("100")))
        self.exchange._api_post.assert_not_called()

    def test_place_order_ws_transport_failure_falls_back_to_rest(self):
        self._set_symbol_map()
        self.exchange._trade_ws_request = AsyncMock(side_effect=GeminiWSTransportError("ws down"))
        self.exchange._api_post = AsyncMock(
            return_value={"order_id": 9876, "timestampms": 1700000000000})

        o_id, ts = self._async_run(self.exchange._place_order(
            order_id="HBOT1", trading_pair="BTC-USD", amount=Decimal("1"),
            trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("100")))

        self.assertEqual("9876", o_id)
        self.assertEqual(1700000000.0, ts)
        _, kwargs = self.exchange._api_post.call_args
        self.assertEqual(CONSTANTS.SIDE_BUY, kwargs["data"]["side"])
        self.assertEqual(CONSTANTS.ORDER_TYPE_LIMIT, kwargs["data"]["type"])
        self.assertNotIn("options", kwargs["data"])

    def test_place_order_ws_ambiguous_failure_reconciles_existing_order(self):
        # Ack timeout / disconnect-after-send: the order may be live. If REST status
        # finds an order with this client id, return it instead of re-placing.
        self._set_symbol_map()
        self.exchange._trade_ws_request = AsyncMock(
            side_effect=GeminiWSAmbiguousResponseError("ack timeout"))
        self.exchange._api_post = AsyncMock(
            return_value={"order_id": 555, "timestampms": 1700000000000, "is_live": True})

        o_id, ts = self._async_run(self.exchange._place_order(
            order_id="HBOT1", trading_pair="BTC-USD", amount=Decimal("1"),
            trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("100")))

        self.assertEqual("555", o_id)
        self.assertEqual(1700000000.0, ts)
        self.exchange._api_post.assert_awaited_once()
        _, kwargs = self.exchange._api_post.call_args
        self.assertEqual(CONSTANTS.ORDER_STATUS_PATH_URL, kwargs["path_url"])
        self.assertEqual("HBOT1", kwargs["data"]["client_order_id"])

    def test_place_order_ws_ambiguous_failure_places_via_rest_when_not_found(self):
        self._set_symbol_map()
        self.exchange._trade_ws_request = AsyncMock(
            side_effect=GeminiWSAmbiguousResponseError("ack timeout"))
        self.exchange._api_post = AsyncMock(side_effect=[
            IOError("OrderNotFound"),
            {"order_id": 9876, "timestampms": 1700000000000},
        ])

        o_id, _ = self._async_run(self.exchange._place_order(
            order_id="HBOT1", trading_pair="BTC-USD", amount=Decimal("1"),
            trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("100")))

        self.assertEqual("9876", o_id)
        self.assertEqual(2, self.exchange._api_post.await_count)
        _, placement_kwargs = self.exchange._api_post.call_args
        self.assertEqual(CONSTANTS.NEW_ORDER_PATH_URL, placement_kwargs["path_url"])

    def test_place_order_ws_ambiguous_failure_unresolved_reconciliation_raises(self):
        # If the reconcile itself fails for a reason other than not-found, the
        # ambiguity stands: raise instead of risking a duplicate placement.
        self._set_symbol_map()
        self.exchange._trade_ws_request = AsyncMock(
            side_effect=GeminiWSAmbiguousResponseError("ack timeout"))
        self.exchange._api_post = AsyncMock(side_effect=IOError("503 Service Unavailable"))

        with self.assertRaises(IOError):
            self._async_run(self.exchange._place_order(
                order_id="HBOT1", trading_pair="BTC-USD", amount=Decimal("1"),
                trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("100")))

        self.exchange._api_post.assert_awaited_once()
        _, kwargs = self.exchange._api_post.call_args
        self.assertEqual(CONSTANTS.ORDER_STATUS_PATH_URL, kwargs["path_url"])

    def test_place_order_ws_server_error_falls_back_to_rest(self):
        self._set_symbol_map()
        self.exchange._trade_ws_request = AsyncMock(return_value={
            "id": "1", "status": 500, "error": {"code": -1000, "msg": "Internal error"}})
        self.exchange._api_post = AsyncMock(
            return_value={"order_id": 1, "timestampms": 0})

        o_id, _ = self._async_run(self.exchange._place_order(
            order_id="HBOT1", trading_pair="BTC-USD", amount=Decimal("1"),
            trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("100")))

        self.assertEqual("1", o_id)

    def test_place_order_rest_fallback_limit_maker_adds_option(self):
        self._set_symbol_map()
        self.exchange._trade_ws_request = AsyncMock(side_effect=GeminiWSTransportError("ws down"))
        self.exchange._api_post = AsyncMock(
            return_value={"order_id": 1, "timestampms": 0})

        self._async_run(self.exchange._place_order(
            order_id="HBOT1", trading_pair="ETH-USD", amount=Decimal("1"),
            trade_type=TradeType.SELL, order_type=OrderType.LIMIT_MAKER, price=Decimal("100")))

        _, kwargs = self.exchange._api_post.call_args
        self.assertEqual(CONSTANTS.SIDE_SELL, kwargs["data"]["side"])
        self.assertEqual([CONSTANTS.ORDER_OPTION_MAKER_OR_CANCEL], kwargs["data"]["options"])

    # ------------------------------------------------------------------
    # MARKET orders — emulated as an immediate-or-cancel "exchange limit"
    # ------------------------------------------------------------------

    def test_supported_order_types_includes_market(self):
        self.assertIn(OrderType.MARKET, self.exchange.supported_order_types())

    def _prime_market_price(self, volume_price="100", top_price="100"):
        # Stand in for the order book: a price that fills the whole volume, the top of
        # book, and an identity quantizer so assertions can reason about exact numbers.
        self.exchange.get_price_for_volume = MagicMock(
            return_value=MagicMock(result_price=Decimal(volume_price)))
        self.exchange.get_price = MagicMock(return_value=Decimal(top_price))
        self.exchange.quantize_order_price = MagicMock(side_effect=lambda tp, p: p)

    def test_place_order_market_buy_uses_rest_ioc_above_market(self):
        self._set_symbol_map()
        self._prime_market_price(volume_price="100")
        self.exchange._trade_ws_request = AsyncMock()
        self.exchange._api_post = AsyncMock(
            return_value={"order_id": 555, "timestampms": 1700000000000})

        o_id, ts = self._async_run(self.exchange._place_order(
            order_id="HBOT1", trading_pair="BTC-USD", amount=Decimal("1"),
            trade_type=TradeType.BUY, order_type=OrderType.MARKET, price=Decimal("NaN")))

        self.assertEqual("555", o_id)
        self.assertGreater(ts, 0)
        # A MARKET order never touches the maker-oriented order-entry websocket.
        self.exchange._trade_ws_request.assert_not_called()
        self.exchange.get_price_for_volume.assert_called_once_with("BTC-USD", True, Decimal("1"))
        _, kwargs = self.exchange._api_post.call_args
        self.assertEqual(CONSTANTS.NEW_ORDER_PATH_URL, kwargs["path_url"])
        data = kwargs["data"]
        self.assertEqual(CONSTANTS.ORDER_TYPE_LIMIT, data["type"])
        self.assertEqual([CONSTANTS.ORDER_OPTION_IMMEDIATE_OR_CANCEL], data["options"])
        self.assertEqual(CONSTANTS.SIDE_BUY, data["side"])
        # Buy is padded ABOVE the fill price so the IOC sweeps the book.
        self.assertGreater(Decimal(data["price"]), Decimal("100"))

    def test_place_order_market_sell_uses_rest_ioc_below_market(self):
        self._set_symbol_map()
        self._prime_market_price(volume_price="100")
        self.exchange._trade_ws_request = AsyncMock()
        self.exchange._api_post = AsyncMock(return_value={"order_id": 7, "timestampms": 0})

        self._async_run(self.exchange._place_order(
            order_id="HBOT1", trading_pair="ETH-USD", amount=Decimal("2"),
            trade_type=TradeType.SELL, order_type=OrderType.MARKET, price=Decimal("NaN")))

        self.exchange._trade_ws_request.assert_not_called()
        _, kwargs = self.exchange._api_post.call_args
        data = kwargs["data"]
        self.assertEqual(CONSTANTS.SIDE_SELL, data["side"])
        self.assertEqual([CONSTANTS.ORDER_OPTION_IMMEDIATE_OR_CANCEL], data["options"])
        # Sell is padded BELOW the fill price (but still positive).
        self.assertLess(Decimal(data["price"]), Decimal("100"))
        self.assertGreater(Decimal(data["price"]), Decimal("0"))

    def test_market_order_price_falls_back_to_top_of_book(self):
        self.exchange.get_price_for_volume = MagicMock(side_effect=ValueError("no depth"))
        self.exchange.get_price = MagicMock(return_value=Decimal("200"))
        self.exchange.quantize_order_price = MagicMock(side_effect=lambda tp, p: p)

        price = self.exchange._market_order_price(
            trading_pair="BTC-USD", trade_type=TradeType.BUY,
            amount=Decimal("1"), price=Decimal("NaN"))

        self.assertGreater(price, Decimal("200"))

    def test_market_order_price_skips_nan_volume_price(self):
        self.exchange.get_price_for_volume = MagicMock(
            return_value=MagicMock(result_price=Decimal("NaN")))
        self.exchange.get_price = MagicMock(return_value=Decimal("300"))
        self.exchange.quantize_order_price = MagicMock(side_effect=lambda tp, p: p)

        price = self.exchange._market_order_price(
            trading_pair="BTC-USD", trade_type=TradeType.BUY,
            amount=Decimal("1"), price=Decimal("NaN"))

        self.assertGreater(price, Decimal("300"))

    def test_market_order_price_uses_fallback_price_when_book_unavailable(self):
        self.exchange.get_price_for_volume = MagicMock(side_effect=ValueError("no book"))
        self.exchange.get_price = MagicMock(side_effect=ValueError("no book"))
        self.exchange.quantize_order_price = MagicMock(side_effect=lambda tp, p: p)

        price = self.exchange._market_order_price(
            trading_pair="BTC-USD", trade_type=TradeType.SELL,
            amount=Decimal("1"), price=Decimal("50"))

        self.assertLess(price, Decimal("50"))
        self.assertGreater(price, Decimal("0"))

    def test_market_order_price_raises_without_any_usable_price(self):
        self.exchange.get_price_for_volume = MagicMock(side_effect=ValueError("no book"))
        self.exchange.get_price = MagicMock(side_effect=ValueError("no book"))

        with self.assertRaises(ValueError):
            self.exchange._market_order_price(
                trading_pair="BTC-USD", trade_type=TradeType.BUY,
                amount=Decimal("1"), price=Decimal("NaN"))

    def test_market_order_price_guards_against_zero_after_quantization(self):
        # A sell whose slippage-adjusted price quantizes down to 0 falls back to the
        # (positive) reference so the order still carries a valid limit price.
        self.exchange.get_price_for_volume = MagicMock(
            return_value=MagicMock(result_price=Decimal("0.0001")))
        self.exchange.get_price = MagicMock(return_value=Decimal("0.0001"))

        def fake_quantize(trading_pair, candidate):
            return Decimal("0") if candidate < Decimal("0.0001") else Decimal("0.0001")

        self.exchange.quantize_order_price = MagicMock(side_effect=fake_quantize)

        price = self.exchange._market_order_price(
            trading_pair="BTC-USD", trade_type=TradeType.SELL,
            amount=Decimal("1"), price=Decimal("NaN"))

        self.assertEqual(Decimal("0.0001"), price)

    def test_market_order_price_buy_caps_at_affordable_quote(self):
        # The +slippage limit would require more quote than the user holds; cap it so
        # Gemini's amount*limit funds check passes, while still >= the sweep reference.
        self.exchange.get_price_for_volume = MagicMock(
            return_value=MagicMock(result_price=Decimal("100")))
        self.exchange.get_price = MagicMock(return_value=Decimal("100"))
        self.exchange.quantize_order_price = MagicMock(side_effect=lambda tp, p: p)
        self.exchange._account_available_balances["USD"] = Decimal("101")  # < 1 * 100 * 1.02

        price = self.exchange._market_order_price(
            trading_pair="BTC-USD", trade_type=TradeType.BUY,
            amount=Decimal("1"), price=Decimal("NaN"))

        self.assertEqual(Decimal("101"), price)
        self.assertLessEqual(price * Decimal("1"), Decimal("101"))  # fundable

    def test_market_order_price_buy_not_capped_when_balance_is_ample(self):
        self.exchange.get_price_for_volume = MagicMock(
            return_value=MagicMock(result_price=Decimal("100")))
        self.exchange.get_price = MagicMock(return_value=Decimal("100"))
        self.exchange.quantize_order_price = MagicMock(side_effect=lambda tp, p: p)
        self.exchange._account_available_balances["USD"] = Decimal("1000000")

        price = self.exchange._market_order_price(
            trading_pair="BTC-USD", trade_type=TradeType.BUY,
            amount=Decimal("1"), price=Decimal("NaN"))

        self.assertEqual(Decimal("102"), price)  # full 2% buffer, uncapped

    def test_market_order_price_buy_caps_below_marginal_sweep_reference(self):
        # The full-depth sweep reference (110) exceeds what the balance can fund (105); the
        # cap must still apply (105), not be skipped — the IOC then fills what it can afford
        # at the cheaper resting prices instead of being rejected for insufficient funds.
        self.exchange.get_price_for_volume = MagicMock(
            return_value=MagicMock(result_price=Decimal("110")))
        self.exchange.get_price = MagicMock(return_value=Decimal("110"))
        self.exchange.quantize_order_price = MagicMock(side_effect=lambda tp, p: p)
        self.exchange._account_available_balances["USD"] = Decimal("105")  # < 110, < 110*1.02

        price = self.exchange._market_order_price(
            trading_pair="BTC-USD", trade_type=TradeType.BUY,
            amount=Decimal("1"), price=Decimal("NaN"))

        self.assertEqual(Decimal("105"), price)
        self.assertLessEqual(price * Decimal("1"), Decimal("105"))  # fundable, not rejected

    def test_affordable_buy_limit_price_guards(self):
        self.assertIsNone(self.exchange._affordable_buy_limit_price("BTC-USD", Decimal("0")))
        self.assertIsNone(self.exchange._affordable_buy_limit_price("BTC-USD", Decimal("1")))
        self.exchange._account_available_balances["USD"] = Decimal("-5")
        self.assertIsNone(self.exchange._affordable_buy_limit_price("BTC-USD", Decimal("1")))
        self.exchange._account_available_balances["USD"] = Decimal("200")
        self.assertEqual(Decimal("100"), self.exchange._affordable_buy_limit_price("BTC-USD", Decimal("2")))

    # ------------------------------------------------------------------
    # Order cancellation — websocket-first
    # ------------------------------------------------------------------

    def test_place_cancel_ws_success(self):
        self._set_symbol_map()
        order = self._start_tracking_limit_buy(order_id="HBOT1", exchange_order_id="123")
        self.exchange._trade_ws_request = AsyncMock(return_value={"id": "1", "status": 200})
        self.exchange._api_post = AsyncMock()

        self.assertTrue(self._async_run(self.exchange._place_cancel("HBOT1", order)))

        self.exchange._api_post.assert_not_called()
        _, kwargs = self.exchange._trade_ws_request.call_args
        self.assertEqual(CONSTANTS.WS_METHOD_ORDER_CANCEL, kwargs["method"])
        self.assertEqual({"orderId": "123"}, kwargs["params"])
        self.assertEqual(CONSTANTS.WS_ORDER_CANCEL_LIMIT_ID, kwargs["throttler_limit_id"])

    def test_place_cancel_ws_not_found_raises_and_matches_predicate(self):
        self._set_symbol_map()
        order = self._start_tracking_limit_buy(order_id="HBOT1", exchange_order_id="123")
        self.exchange._trade_ws_request = AsyncMock(return_value={
            "id": "1", "status": 400,
            "error": {"code": -1013, "msg": "Invalid parameters - order not found or already filled"}})
        self.exchange._api_post = AsyncMock()

        with self.assertRaises(GeminiWSRejectionError) as context:
            self._async_run(self.exchange._place_cancel("HBOT1", order))

        self.exchange._api_post.assert_not_called()
        self.assertTrue(self.exchange._is_order_not_found_during_cancelation_error(context.exception))

    def test_place_cancel_ws_transport_failure_falls_back_to_rest(self):
        self._set_symbol_map()
        order = self._start_tracking_limit_buy(order_id="HBOT1", exchange_order_id="123")
        self.exchange._trade_ws_request = AsyncMock(side_effect=GeminiWSTransportError("ws down"))
        self.exchange._api_post = AsyncMock(return_value={"is_cancelled": True})

        self.assertTrue(self._async_run(self.exchange._place_cancel("HBOT1", order)))
        _, kwargs = self.exchange._api_post.call_args
        self.assertEqual(123, kwargs["data"]["order_id"])

    def test_place_cancel_rest_fallback_returns_false(self):
        self._set_symbol_map()
        order = self._start_tracking_limit_buy(order_id="HBOT1", exchange_order_id="123")
        self.exchange._trade_ws_request = AsyncMock(side_effect=GeminiWSTransportError("ws down"))
        self.exchange._api_post = AsyncMock(return_value={"is_cancelled": False})

        self.assertFalse(self._async_run(self.exchange._place_cancel("HBOT1", order)))

    # ------------------------------------------------------------------
    # Trade websocket plumbing
    # ------------------------------------------------------------------

    def test_extract_exchange_order_id_variants(self):
        extract = GeminiExchange._extract_exchange_order_id
        self.assertEqual("1", extract({"orderId": 1}))
        self.assertEqual("2", extract({"order_id": "2"}))
        self.assertEqual("3", extract({"i": 3}))
        self.assertEqual("5", extract({"order": {"orderId": 5}}))
        # the generic "id" key may echo the request id — it must NOT be used
        self.assertIsNone(extract({"id": "4"}))
        self.assertIsNone(extract({}))
        self.assertIsNone(extract(None))
        self.assertIsNone(extract({"orderId": ""}))
        self.assertIsNone(extract(["not", "a", "dict"]))

    def test_raise_for_ws_error_classification(self):
        GeminiExchange._raise_for_ws_error({"status": 200, "result": {}})  # no raise
        with self.assertRaises(GeminiWSRejectionError):
            GeminiExchange._raise_for_ws_error(
                {"status": 400, "error": {"code": -1013, "msg": "Invalid parameters"}})
        for status in (401, 429, 500, None):
            with self.assertRaises(GeminiWSTransportError):
                GeminiExchange._raise_for_ws_error({"status": status, "error": {}})

    def test_trade_ws_request_round_trip(self):
        mock_ws = AsyncMock()

        async def fake_send(request):
            payload = request.payload
            self.assertEqual({"id": payload["id"],
                              "method": CONSTANTS.WS_METHOD_PING,
                              "params": {}}, payload)
            self.exchange._trade_ws_pending_requests[payload["id"]].set_result(
                {"id": payload["id"], "status": 200, "result": {}})

        mock_ws.send = AsyncMock(side_effect=fake_send)
        self.exchange._connected_trade_ws = AsyncMock(return_value=mock_ws)

        response = self._async_run(self.exchange._trade_ws_request(
            method=CONSTANTS.WS_METHOD_PING, params={},
            throttler_limit_id=CONSTANTS.NEW_ORDER_PATH_URL))

        self.assertEqual(200, response["status"])
        self.assertEqual({}, self.exchange._trade_ws_pending_requests)

    def test_trade_ws_request_timeout_raises_ambiguous_error(self):
        mock_ws = AsyncMock()
        self.exchange._connected_trade_ws = AsyncMock(return_value=mock_ws)

        with patch.object(CONSTANTS, "WS_ORDER_REQUEST_TIMEOUT", 0.05):
            # An ack timeout means the request may have executed — must be the
            # ambiguous subtype so _place_order reconciles instead of re-placing.
            with self.assertRaises(GeminiWSAmbiguousResponseError):
                self._async_run(self.exchange._trade_ws_request(
                    method=CONSTANTS.WS_METHOD_ORDER_PLACE, params={},
                    throttler_limit_id=CONSTANTS.NEW_ORDER_PATH_URL))
        self.assertEqual({}, self.exchange._trade_ws_pending_requests)

    def test_trade_ws_request_connect_failure_raises_transport_error(self):
        self.exchange._connected_trade_ws = AsyncMock(side_effect=Exception("no network"))

        with self.assertRaises(GeminiWSTransportError):
            self._async_run(self.exchange._trade_ws_request(
                method=CONSTANTS.WS_METHOD_ORDER_PLACE, params={},
                throttler_limit_id=CONSTANTS.NEW_ORDER_PATH_URL))

    def test_trade_ws_request_send_failure_raises_transport_error(self):
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock(side_effect=Exception("broken pipe"))
        self.exchange._connected_trade_ws = AsyncMock(return_value=mock_ws)

        with self.assertRaises(GeminiWSTransportError):
            self._async_run(self.exchange._trade_ws_request(
                method=CONSTANTS.WS_METHOD_ORDER_PLACE, params={},
                throttler_limit_id=CONSTANTS.NEW_ORDER_PATH_URL))
        self.assertEqual({}, self.exchange._trade_ws_pending_requests)

    def test_trade_ws_listener_routes_acks_and_resets_on_exit(self):
        async def scenario():
            ack_future = asyncio.get_running_loop().create_future()
            unrelated_future = asyncio.get_running_loop().create_future()
            self.exchange._trade_ws_pending_requests["5"] = ack_future
            self.exchange._trade_ws_pending_requests["6"] = unrelated_future
            fake_ws = _FakeTradeWS(messages=[
                WSResponse(data="not a dict"),
                WSResponse(data={"e": "executionReport", "X": "NEW"}),  # stream event, no id match
                WSResponse(data={"id": "5", "status": 200, "result": {"orderId": 1}}),
            ])
            self.exchange._trade_ws = fake_ws
            await self.exchange._trade_ws_listener(fake_ws)
            return ack_future, unrelated_future, fake_ws

        ack_future, unrelated_future, fake_ws = self._async_run(scenario())

        self.assertEqual(200, ack_future.result()["status"])
        # The connection ended, so the listener must reset state and fail leftovers
        # as ambiguous (their requests were already sent on the dying socket).
        self.assertIsNone(self.exchange._trade_ws)
        self.assertEqual({}, self.exchange._trade_ws_pending_requests)
        self.assertIsInstance(unrelated_future.exception(), GeminiWSAmbiguousResponseError)
        self.assertTrue(fake_ws.disconnected)

    def test_reset_trade_ws_ignores_stale_connection(self):
        async def scenario():
            current_ws = AsyncMock()
            stale_ws = AsyncMock()
            self.exchange._trade_ws = current_ws
            await self.exchange._reset_trade_ws(stale_ws)
            return current_ws

        current_ws = self._async_run(scenario())
        self.assertIs(current_ws, self.exchange._trade_ws)
        current_ws.disconnect.assert_not_called()
        self.exchange._trade_ws = None  # cleanup for other tests

    def test_stop_network_resets_trade_ws(self):
        async def scenario():
            mock_ws = AsyncMock()
            self.exchange._trade_ws = mock_ws
            pending = asyncio.get_running_loop().create_future()
            self.exchange._trade_ws_pending_requests["1"] = pending
            await self.exchange.stop_network()
            return mock_ws, pending

        mock_ws, pending = self._async_run(scenario())
        mock_ws.disconnect.assert_awaited_once()
        self.assertIsNone(self.exchange._trade_ws)
        self.assertIsInstance(pending.exception(), GeminiWSTransportError)
        self.assertTrue(self.exchange._trade_ws_stopped)

    def test_start_network_clears_trade_ws_stop_state(self):
        self.exchange._trade_ws_stopped = True
        self.exchange._trade_ws_last_connect_failure = 12345.0

        with patch.object(ExchangePyBase, "start_network", new_callable=AsyncMock):
            self._async_run(self.exchange.start_network())

        self.assertFalse(self.exchange._trade_ws_stopped)
        self.assertEqual(0.0, self.exchange._trade_ws_last_connect_failure)
        # trading is not required on this exchange — no maintenance loop
        self.assertIsNone(self.exchange._trade_ws_maintenance_task)

    def test_status_dict_gates_on_trade_websocket(self):
        trading_exchange = GeminiExchange(
            gemini_api_key="test_key",
            gemini_api_secret="test_secret",
            trading_pairs=["BTC-USD"],
            trading_required=True,
        )
        self.assertFalse(trading_exchange.status_dict["trade_websocket_connected"])
        self.assertFalse(trading_exchange.ready)

        trading_exchange._trade_ws = AsyncMock()
        self.assertTrue(trading_exchange.status_dict["trade_websocket_connected"])

        # non-trading connectors are not gated on the order-entry websocket
        self.assertTrue(self.exchange.status_dict["trade_websocket_connected"])

    def test_start_network_spawns_and_stop_network_cancels_maintenance(self):
        trading_exchange = GeminiExchange(
            gemini_api_key="test_key",
            gemini_api_secret="test_secret",
            trading_pairs=["BTC-USD"],
            trading_required=True,
        )
        trading_exchange._web_assistants_factory.get_ws_assistant = AsyncMock(
            side_effect=Exception("offline"))

        async def scenario():
            with patch.object(ExchangePyBase, "start_network", new_callable=AsyncMock), \
                    patch.object(ExchangePyBase, "stop_network", new_callable=AsyncMock):
                await trading_exchange.start_network()
                spawned_task = trading_exchange._trade_ws_maintenance_task
                await asyncio.sleep(0.05)  # let the loop attempt (and fail) a connect
                await trading_exchange.stop_network()
                remaining_task = trading_exchange._trade_ws_maintenance_task
                await asyncio.sleep(0)  # let the cancellation land
                return spawned_task, remaining_task

        spawned_task, remaining_task = self._async_run(scenario())

        self.assertIsNotNone(spawned_task)
        self.assertIsNone(remaining_task)
        self.assertTrue(spawned_task.done())
        # the failed eager connect armed the cooldown
        self.assertGreater(trading_exchange._trade_ws_last_connect_failure, 0)
        self.assertTrue(trading_exchange._trade_ws_stopped)

    def test_real_lifecycle_start_network_enables_trade_websocket(self):
        # Regression for a live incident: ExchangePyBase.start_network's FIRST
        # statement is `await self.stop_network()`, which dispatches to our override
        # and sets the stop flag. If start_network cleared the flags before super()
        # instead of after, the trade websocket stayed gated forever and every order
        # silently fell back to REST. This test runs the REAL base lifecycle methods.
        trading_exchange = GeminiExchange(
            gemini_api_key="test_key",
            gemini_api_secret="test_secret",
            trading_pairs=["BTC-USD"],
            trading_required=True,
        )
        fake_ws = _ScriptedWSAssistant()
        trading_exchange._web_assistants_factory.get_ws_assistant = AsyncMock(return_value=fake_ws)
        # stub the network-touching components the base lifecycle starts/stops
        trading_exchange._order_book_tracker = MagicMock()
        trading_exchange._user_stream_tracker = AsyncMock()
        trading_exchange._user_stream_tracker.data_source.last_recv_time = 1.0
        trading_exchange._create_user_stream_tracker_task = lambda: None
        trading_exchange._trading_rules_polling_loop = AsyncMock()
        trading_exchange._trading_fees_polling_loop = AsyncMock()
        trading_exchange._status_polling_loop = AsyncMock()
        trading_exchange._user_stream_event_listener = AsyncMock()
        trading_exchange._lost_orders_update_polling_loop = AsyncMock()

        async def scenario():
            with patch.object(CONSTANTS, "WS_MAINTENANCE_INTERVAL", 0.01):
                await trading_exchange.start_network()
                stopped_after_start = trading_exchange._trade_ws_stopped
                for _ in range(100):
                    if trading_exchange._trade_ws is fake_ws:
                        break
                    await asyncio.sleep(0.01)
                connected = trading_exchange._trade_ws is fake_ws
                ws_ready = trading_exchange.status_dict["trade_websocket_connected"]
                await trading_exchange.stop_network()
                await asyncio.sleep(0)
                return stopped_after_start, connected, ws_ready

        stopped_after_start, connected, ws_ready = self._async_run(scenario())

        self.assertFalse(stopped_after_start)
        self.assertTrue(connected)
        self.assertTrue(ws_ready)
        self.assertTrue(trading_exchange._trade_ws_stopped)
        self.assertIsNone(trading_exchange._trade_ws)
        self.assertIsNone(trading_exchange._trade_ws_maintenance_task)
        self.assertTrue(fake_ws.disconnected)

    def test_trade_ws_maintenance_loop_connects_and_reconnects(self):
        fake_ws_1 = _ScriptedWSAssistant()
        fake_ws_2 = _ScriptedWSAssistant()

        async def scenario():
            self.exchange._web_assistants_factory.get_ws_assistant = AsyncMock(
                side_effect=[fake_ws_1, fake_ws_2])
            with patch.object(CONSTANTS, "WS_MAINTENANCE_INTERVAL", 0.01):
                loop_task = asyncio.get_running_loop().create_task(
                    self.exchange._trade_ws_maintenance_loop())
                for _ in range(100):
                    if self.exchange._trade_ws is fake_ws_1:
                        break
                    await asyncio.sleep(0.01)
                self.assertIs(fake_ws_1, self.exchange._trade_ws)

                # drop the connection: the loop must bring up a fresh one by itself
                await self.exchange._reset_trade_ws(self.exchange._trade_ws)
                for _ in range(100):
                    if self.exchange._trade_ws is fake_ws_2:
                        break
                    await asyncio.sleep(0.01)
                self.assertIs(fake_ws_2, self.exchange._trade_ws)

                loop_task.cancel()
                await self.exchange._reset_trade_ws(self.exchange._trade_ws)
                await asyncio.sleep(0)

        self._async_run(scenario())
        self.assertTrue(fake_ws_1.disconnected)
        self.assertTrue(fake_ws_2.disconnected)

    def test_rate_limits_linked_ids_are_defined(self):
        defined_ids = {limit.limit_id for limit in CONSTANTS.RATE_LIMITS}
        for limit in CONSTANTS.RATE_LIMITS:
            for linked in limit.linked_limits:
                self.assertIn(linked.limit_id, defined_ids)
        self.assertIn(CONSTANTS.WS_ORDER_PLACE_LIMIT_ID, defined_ids)
        self.assertIn(CONSTANTS.WS_ORDER_CANCEL_LIMIT_ID, defined_ids)

    def test_connected_trade_ws_refuses_when_stopped(self):
        self.exchange._trade_ws_stopped = True

        with self.assertRaises(GeminiWSTransportError):
            self._async_run(self.exchange._connected_trade_ws())

    def test_connected_trade_ws_timeboxes_connect_and_sets_cooldown(self):
        hanging_ws = AsyncMock()

        async def hang(**kwargs):
            await asyncio.sleep(10)

        hanging_ws.connect = AsyncMock(side_effect=hang)
        self.exchange._web_assistants_factory.get_ws_assistant = AsyncMock(return_value=hanging_ws)

        with patch.object(CONSTANTS, "WS_CONNECT_TIMEOUT", 0.05):
            with self.assertRaises(GeminiWSTransportError) as context:
                self._async_run(self.exchange._trade_ws_request(
                    method=CONSTANTS.WS_METHOD_ORDER_PLACE, params={},
                    throttler_limit_id=CONSTANTS.NEW_ORDER_PATH_URL))

        # A connect failure happens before anything is sent: it must be the plain
        # (safe-to-retry) transport error, never the ambiguous subtype.
        self.assertNotIsInstance(context.exception, GeminiWSAmbiguousResponseError)
        self.assertGreater(self.exchange._trade_ws_last_connect_failure, 0)
        hanging_ws.disconnect.assert_awaited()

    def test_connected_trade_ws_cooldown_blocks_reconnect_attempts(self):
        self.exchange._trade_ws_last_connect_failure = self.exchange._time()
        factory_mock = AsyncMock()
        self.exchange._web_assistants_factory.get_ws_assistant = factory_mock

        with self.assertRaises(GeminiWSTransportError):
            self._async_run(self.exchange._connected_trade_ws())

        factory_mock.assert_not_called()

    def test_resolve_acked_order_reconcile_error_raises_without_rest_placement(self):
        # Reconcile fails for a reason other than not-found while resolving an acked
        # order's id: the order's existence is unknown, so raise — never re-place.
        self._set_symbol_map()
        self.exchange.start_tracking_order(
            order_id="HBOT1", exchange_order_id=None, trading_pair="BTC-USD",
            order_type=OrderType.LIMIT, trade_type=TradeType.BUY,
            price=Decimal("100"), amount=Decimal("1"))
        self.exchange._trade_ws_request = AsyncMock(
            return_value={"id": "1", "status": 200, "result": {}})
        self.exchange._api_post = AsyncMock(side_effect=IOError("503 Service Unavailable"))

        with patch("hummingbot.core.data_type.in_flight_order.GET_EX_ORDER_ID_TIMEOUT", 0.05):
            with self.assertRaises(IOError):
                self._async_run(self.exchange._place_order(
                    order_id="HBOT1", trading_pair="BTC-USD", amount=Decimal("1"),
                    trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("100")))

        self.exchange._api_post.assert_awaited_once()

    def test_place_cancel_without_exchange_order_id_times_out(self):
        self._set_symbol_map()
        self.exchange.start_tracking_order(
            order_id="HBOT1", exchange_order_id=None, trading_pair="BTC-USD",
            order_type=OrderType.LIMIT, trade_type=TradeType.BUY,
            price=Decimal("100"), amount=Decimal("1"))
        order = self.exchange.in_flight_orders["HBOT1"]

        # The framework's _execute_order_cancel treats this asyncio.TimeoutError as
        # "order has no exchange id yet" and defers the cancel.
        with patch("hummingbot.core.data_type.in_flight_order.GET_EX_ORDER_ID_TIMEOUT", 0.05):
            with self.assertRaises(asyncio.TimeoutError):
                self._async_run(self.exchange._place_cancel("HBOT1", order))

    def test_connected_trade_ws_stopped_during_handshake_tears_down(self):
        fake_ws = AsyncMock()

        async def connect_then_stopped(**kwargs):
            self.exchange._trade_ws_stopped = True

        fake_ws.connect = AsyncMock(side_effect=connect_then_stopped)
        fake_ws.disconnect = AsyncMock(side_effect=Exception("boom"))  # must be swallowed
        self.exchange._web_assistants_factory.get_ws_assistant = AsyncMock(return_value=fake_ws)

        with self.assertRaises(GeminiWSTransportError):
            self._async_run(self.exchange._connected_trade_ws())

        fake_ws.disconnect.assert_awaited_once()
        self.assertIsNone(self.exchange._trade_ws)

    def test_trade_ws_listener_resets_on_unexpected_error(self):
        async def scenario():
            class _ExplodingWS:
                disconnected = False

                async def iter_messages(self):
                    raise RuntimeError("boom")
                    yield  # pragma: no cover

                async def disconnect(self):
                    self.disconnected = True

            exploding_ws = _ExplodingWS()
            self.exchange._trade_ws = exploding_ws
            await self.exchange._trade_ws_listener(exploding_ws)
            return exploding_ws

        exploding_ws = self._async_run(scenario())
        self.assertIsNone(self.exchange._trade_ws)
        self.assertTrue(exploding_ws.disconnected)

    def test_reset_trade_ws_with_none_is_noop(self):
        self._async_run(self.exchange._reset_trade_ws(None))
        self.assertIsNone(self.exchange._trade_ws)

    def test_trade_ws_round_trip_through_real_plumbing(self):
        # Drives the real _connected_trade_ws -> _trade_ws_listener -> pending-future
        # chain (only the WSAssistant itself is faked): handshake auth headers,
        # connection reuse, lazy reconnect after a drop, and stop_network teardown.
        self._set_symbol_map()
        fake_ws_1 = _ScriptedWSAssistant()
        fake_ws_2 = _ScriptedWSAssistant()
        self.exchange._api_post = AsyncMock()

        async def scenario():
            self.exchange._web_assistants_factory.get_ws_assistant = AsyncMock(
                side_effect=[fake_ws_1, fake_ws_2])
            placement_1 = await self.exchange._place_order(
                order_id="HBOT1", trading_pair="BTC-USD", amount=Decimal("1"),
                trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("100"))
            placement_2 = await self.exchange._place_order(
                order_id="HBOT2", trading_pair="BTC-USD", amount=Decimal("1"),
                trade_type=TradeType.SELL, order_type=OrderType.LIMIT, price=Decimal("101"))
            connections_after_two = self.exchange._web_assistants_factory.get_ws_assistant.await_count
            # simulate a dropped connection: the next request reconnects lazily
            await self.exchange._reset_trade_ws(self.exchange._trade_ws)
            placement_3 = await self.exchange._place_order(
                order_id="HBOT3", trading_pair="BTC-USD", amount=Decimal("1"),
                trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("99"))
            await self.exchange.stop_network()
            stopped_error = None
            try:
                await self.exchange._connected_trade_ws()
            except GeminiWSTransportError as error:
                stopped_error = error
            await asyncio.sleep(0)  # let the cancelled listener task finish
            return placement_1, placement_2, connections_after_two, placement_3, stopped_error

        placement_1, placement_2, connections_after_two, placement_3, stopped_error = (
            self._async_run(scenario()))

        self.assertEqual("4242", placement_1[0])
        self.assertEqual("4242", placement_2[0])
        self.assertEqual(1, connections_after_two)  # second order reused the socket
        self.assertEqual("4242", placement_3[0])  # third order reconnected lazily
        self.assertIsNotNone(stopped_error)
        self.exchange._api_post.assert_not_called()

        # the handshake carried the header-based auth to the right url
        self.assertEqual(1, len(fake_ws_1.connect_calls))
        self.assertEqual(CONSTANTS.WSS_URL, fake_ws_1.connect_calls[0]["ws_url"])
        headers = fake_ws_1.connect_calls[0]["ws_headers"]
        for header in ("X-GEMINI-APIKEY", "X-GEMINI-NONCE",
                       "X-GEMINI-PAYLOAD", "X-GEMINI-SIGNATURE"):
            self.assertIn(header, headers)

        # the order params flowed through the real request pipeline
        sent = fake_ws_1.sent_payloads[0]
        self.assertEqual(CONSTANTS.WS_METHOD_ORDER_PLACE, sent["method"])
        self.assertEqual("HBOT1", sent["params"]["clientOrderId"])

        # teardown left nothing behind
        self.assertTrue(fake_ws_1.disconnected)
        self.assertTrue(fake_ws_2.disconnected)
        self.assertIsNone(self.exchange._trade_ws)
        self.assertIsNone(self.exchange._trade_ws_listener_task)
        self.assertEqual({}, self.exchange._trade_ws_pending_requests)

    # ------------------------------------------------------------------
    # Trading rules
    # ------------------------------------------------------------------

    def test_format_trading_rules(self):
        self._set_symbol_map()
        mock_assistant = AsyncMock()
        mock_assistant.execute_request = AsyncMock(return_value={
            "min_order_size": "0.001",
            "tick_size": "0.000001",
            "quote_increment": "0.01",
        })
        self.exchange._web_assistants_factory.get_rest_assistant = AsyncMock(return_value=mock_assistant)

        rules = self._async_run(self.exchange._format_trading_rules(["btcusd", "ethusd", "unknownxyz"]))

        # unknownxyz is not in the symbol map and is skipped
        self.assertEqual(2, len(rules))
        rule = next(r for r in rules if r.trading_pair == "BTC-USD")
        self.assertEqual(Decimal("0.001"), rule.min_order_size)
        self.assertEqual(Decimal("0.01"), rule.min_price_increment)

    def test_format_trading_rules_only_fetches_configured_pairs(self):
        # The symbol map holds every Gemini symbol; the per-symbol details requests
        # must be limited to the configured trading pairs to respect the 120/min
        # public budget.
        self.exchange._set_trading_pair_symbol_map(
            bidict({"btcusd": "BTC-USD", "ethusd": "ETH-USD", "solusd": "SOL-USD"}))
        mock_assistant = AsyncMock()
        mock_assistant.execute_request = AsyncMock(return_value={
            "min_order_size": "0.001",
            "tick_size": "0.000001",
            "quote_increment": "0.01",
        })
        self.exchange._web_assistants_factory.get_rest_assistant = AsyncMock(return_value=mock_assistant)

        rules = self._async_run(self.exchange._format_trading_rules(["btcusd", "ethusd", "solusd"]))

        # SOL-USD maps but is not a configured pair — no details request for it
        self.assertEqual(2, mock_assistant.execute_request.await_count)
        self.assertEqual({"BTC-USD", "ETH-USD"}, {rule.trading_pair for rule in rules})

    def test_format_trading_rules_skips_on_error(self):
        self._set_symbol_map()
        mock_assistant = AsyncMock()
        mock_assistant.execute_request = AsyncMock(side_effect=Exception("details unavailable"))
        self.exchange._web_assistants_factory.get_rest_assistant = AsyncMock(return_value=mock_assistant)
        rules = self._async_run(self.exchange._format_trading_rules(["btcusd"]))
        self.assertEqual(0, len(rules))

    # ------------------------------------------------------------------
    # Order status
    # ------------------------------------------------------------------

    def _request_status(self, response):
        order = self._start_tracking_limit_buy(order_id="HBOT1", exchange_order_id="123")
        self.exchange._api_post = AsyncMock(return_value=response)
        return self._async_run(self.exchange._request_order_status(order))

    def test_request_order_status_cancelled(self):
        update = self._request_status({"order_id": 123, "is_cancelled": True, "timestampms": 1700000000000})
        self.assertEqual(OrderState.CANCELED, update.new_state)

    def test_request_order_status_live(self):
        update = self._request_status({"order_id": 123, "is_live": True, "remaining_amount": "1"})
        self.assertEqual(OrderState.OPEN, update.new_state)

    def test_request_order_status_closed(self):
        update = self._request_status({"order_id": 123, "remaining_amount": "0"})
        self.assertEqual(OrderState.FILLED, update.new_state)

    def test_request_order_status_partial_falls_back_to_live(self):
        update = self._request_status({"order_id": 123, "remaining_amount": "0.5"})
        self.assertEqual(OrderState.OPEN, update.new_state)

    # ------------------------------------------------------------------
    # Trade updates
    # ------------------------------------------------------------------

    def test_all_trade_updates_for_order(self):
        self._set_symbol_map()
        order = self._start_tracking_limit_buy(order_id="HBOT1", exchange_order_id="100234")
        self.exchange._api_post = AsyncMock(return_value=[
            {"tid": 1, "order_id": 100234, "amount": "0.5", "price": "100",
             "fee_amount": "0.1", "fee_currency": "USD", "timestampms": 1700000000000},
            {"tid": 2, "order_id": 999, "amount": "1", "price": "100",
             "fee_amount": "0", "fee_currency": "USD", "timestampms": 1700000000000},
        ])
        updates = self._async_run(self.exchange._all_trade_updates_for_order(order))
        self.assertEqual(1, len(updates))
        self.assertEqual("1", updates[0].trade_id)
        self.assertEqual(Decimal("0.5"), updates[0].fill_base_amount)

    def test_all_trade_updates_for_order_handles_exception(self):
        self._set_symbol_map()
        order = self._start_tracking_limit_buy(order_id="HBOT1", exchange_order_id="100234")
        self.exchange._api_post = AsyncMock(side_effect=Exception("boom"))
        updates = self._async_run(self.exchange._all_trade_updates_for_order(order))
        self.assertEqual([], updates)

    def test_all_trade_updates_for_order_no_exchange_id(self):
        order = self._start_tracking_limit_buy(order_id="HBOT1", exchange_order_id="100234")
        order.update_exchange_order_id(None)
        updates = self._async_run(self.exchange._all_trade_updates_for_order(order))
        self.assertEqual([], updates)

    # ------------------------------------------------------------------
    # Balances
    # ------------------------------------------------------------------

    def test_update_balances(self):
        self.exchange._api_post = AsyncMock(return_value=[
            {"currency": "BTC", "amount": "2", "available": "1.5"},
            {"currency": "USD", "amount": "1000", "available": "900"},
            {"currency": "GEMI-BTC2602-HI", "amount": "5", "available": "5"},  # skipped (hyphen)
        ])
        self.exchange._account_balances["OLD"] = Decimal("1")
        self.exchange._account_available_balances["OLD"] = Decimal("1")

        self._async_run(self.exchange._update_balances())

        self.assertEqual(Decimal("2"), self.exchange._account_balances["BTC"])
        self.assertEqual(Decimal("1.5"), self.exchange._account_available_balances["BTC"])
        self.assertEqual(Decimal("1000"), self.exchange._account_balances["USD"])
        self.assertNotIn("GEMI-BTC2602-HI", self.exchange._account_balances)
        self.assertNotIn("OLD", self.exchange._account_balances)

    def test_update_balances_raises_on_error(self):
        self.exchange._api_post = AsyncMock(side_effect=Exception("balance error"))
        with self.assertRaises(Exception):
            self._async_run(self.exchange._update_balances())

    def test_update_balances_skips_negative_dust(self):
        # Gemini reports sub-cent negative USD dust next to a real USDC holding; the dust
        # must not surface in the balance view or feed a negative into budget checks.
        self.exchange._api_post = AsyncMock(return_value=[
            {"currency": "USDC", "amount": "100", "available": "100"},
            {"currency": "USD", "amount": "-0.0020", "available": "-0.0020"},
        ])
        self.exchange._account_balances["USD"] = Decimal("-0.0020")
        self.exchange._account_available_balances["USD"] = Decimal("-0.0020")

        self._async_run(self.exchange._update_balances())

        self.assertEqual(Decimal("100"), self.exchange._account_balances["USDC"])
        self.assertNotIn("USD", self.exchange._account_balances)
        self.assertNotIn("USD", self.exchange._account_available_balances)

    def test_update_balances_master_key_error_is_actionable(self):
        self.exchange._api_post = AsyncMock(side_effect=IOError(
            'Error executing request POST https://api.gemini.com/v1/balances. HTTP status '
            'is 400. Error: {"result":"error","reason":"MissingAccounts","message":'
            '"Expected a JSON payload with accounts"}'))

        with self.assertRaises(IOError) as ctx:
            self._async_run(self.exchange._update_balances())

        self.assertIn("Master API key", str(ctx.exception))
        self.assertIn("account-scoped", str(ctx.exception))

    # ------------------------------------------------------------------
    # Last traded price
    # ------------------------------------------------------------------

    def test_get_last_traded_price(self):
        self._set_symbol_map()
        self.exchange._api_request = AsyncMock(return_value={"close": "123.45"})
        price = self._async_run(self.exchange._get_last_traded_price("BTC-USD"))
        self.assertEqual(123.45, price)
        # the formatted path is not a registered throttler id — the template must be
        # passed explicitly or the real throttler raises on the unknown id
        _, kwargs = self.exchange._api_request.call_args
        self.assertEqual(CONSTANTS.TICKER_PATH_URL, kwargs["limit_id"])

    # ------------------------------------------------------------------
    # User stream — balance updates
    # ------------------------------------------------------------------

    def test_user_stream_balance_update(self):
        balance_event = {
            "e": CONSTANTS.WS_EVENT_BALANCE_UPDATE,
            "E": 1700000000000,
            "B": [{"a": "USD", "f": "207.39"}, {"a": "", "f": "1"}],
        }
        self._drive_user_stream([balance_event])
        self.assertEqual(Decimal("207.39"), self.exchange._account_available_balances["USD"])
        self.assertEqual(Decimal("207.39"), self.exchange._account_balances["USD"])

    def test_user_stream_balance_update_drops_non_positive(self):
        # A balanceUpdate that drives an asset to sub-cent negative dust removes it from
        # the tracked balances rather than recording a negative figure.
        self.exchange._account_available_balances["USD"] = Decimal("5")
        self.exchange._account_balances["USD"] = Decimal("5")
        balance_event = {
            "e": CONSTANTS.WS_EVENT_BALANCE_UPDATE,
            "E": 1700000000000,
            "B": [{"a": "USD", "f": "-0.0020"}],
        }
        self._drive_user_stream([balance_event])
        self.assertNotIn("USD", self.exchange._account_balances)
        self.assertNotIn("USD", self.exchange._account_available_balances)

    def test_user_stream_handles_unexpected_error(self):
        # A malformed order event (status present but bad data) should be caught and logged
        with patch.object(self.exchange, "_sleep", new_callable=AsyncMock):
            bad_event = {"X": "FILLED", "c": "HBOT1", "Z": "not-a-number", "t": "t1"}
            order = self._start_tracking_limit_buy(order_id="HBOT1", exchange_order_id="123")  # noqa: F841
            self._drive_user_stream([bad_event])
        # No fills recorded because the Decimal conversion failed and was handled
        self.assertEqual(0, len(self.exchange.in_flight_orders["HBOT1"].order_fills))
