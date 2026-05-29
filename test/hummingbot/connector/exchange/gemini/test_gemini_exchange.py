import asyncio
from decimal import Decimal
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from bidict import bidict

from hummingbot.connector.exchange.gemini import gemini_constants as CONSTANTS
from hummingbot.connector.exchange.gemini.gemini_exchange import GeminiExchange
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee


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
    # Order placement / cancellation
    # ------------------------------------------------------------------

    def test_place_order_limit(self):
        self._set_symbol_map()
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

    def test_place_order_limit_maker_adds_option(self):
        self._set_symbol_map()
        self.exchange._api_post = AsyncMock(
            return_value={"order_id": 1, "timestampms": 0})
        self._async_run(self.exchange._place_order(
            order_id="HBOT1", trading_pair="ETH-USD", amount=Decimal("1"),
            trade_type=TradeType.SELL, order_type=OrderType.LIMIT_MAKER, price=Decimal("100")))
        _, kwargs = self.exchange._api_post.call_args
        self.assertEqual(CONSTANTS.SIDE_SELL, kwargs["data"]["side"])
        self.assertEqual(["maker-or-cancel"], kwargs["data"]["options"])

    def test_place_cancel_returns_true(self):
        self._set_symbol_map()
        order = self._start_tracking_limit_buy(order_id="HBOT1", exchange_order_id="123")
        self.exchange._api_post = AsyncMock(return_value={"is_cancelled": True})
        self.assertTrue(self._async_run(self.exchange._place_cancel("HBOT1", order)))

    def test_place_cancel_returns_false(self):
        self._set_symbol_map()
        order = self._start_tracking_limit_buy(order_id="HBOT1", exchange_order_id="123")
        self.exchange._api_post = AsyncMock(return_value={"is_cancelled": False})
        self.assertFalse(self._async_run(self.exchange._place_cancel("HBOT1", order)))

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

    # ------------------------------------------------------------------
    # Last traded price
    # ------------------------------------------------------------------

    def test_get_last_traded_price(self):
        self._set_symbol_map()
        self.exchange._api_request = AsyncMock(return_value={"close": "123.45"})
        price = self._async_run(self.exchange._get_last_traded_price("BTC-USD"))
        self.assertEqual(123.45, price)

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

    def test_user_stream_handles_unexpected_error(self):
        # A malformed order event (status present but bad data) should be caught and logged
        with patch.object(self.exchange, "_sleep", new_callable=AsyncMock):
            bad_event = {"X": "FILLED", "c": "HBOT1", "Z": "not-a-number", "t": "t1"}
            order = self._start_tracking_limit_buy(order_id="HBOT1", exchange_order_id="123")  # noqa: F841
            self._drive_user_stream([bad_event])
        # No fills recorded because the Decimal conversion failed and was handled
        self.assertEqual(0, len(self.exchange.in_flight_orders["HBOT1"].order_fills))
