import asyncio
from decimal import Decimal
from unittest import TestCase
from unittest.mock import AsyncMock

from hummingbot.connector.exchange.gemini.gemini_exchange import GeminiExchange
from hummingbot.core.data_type.common import OrderType, TradeType
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
