"""
Unit tests for LmexPerpetualUserStreamDataSource.

Covers:
  - Exported event-key constants: ORDERS_EVENT_KEY, TRADES_EVENT_KEY,
    POSITIONS_EVENT_KEY, WALLET_EVENT_KEY
  - _poll_and_emit: wallet event always emitted, orders/trades/positions
    emitted only when non-empty, exceptions in sub-polls continue silently
  - _connected_websocket_assistant / _subscribe_channels: NotImplementedError stubs

All tests are pure unit tests using stdlib + unittest + unittest.mock.
No live network calls are made.
"""

import asyncio
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Cython stub shim — compiled extensions not available without a build step.
# Installed before any source module is imported.
# ---------------------------------------------------------------------------

def _stub(name: str, **attrs):
    """Install a lightweight fake module into sys.modules."""
    if name not in sys.modules:
        m = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(m, k, v)
        sys.modules[name] = m


_stub(
    "hummingbot.core.data_type.order_book",
    OrderBook=type("OrderBook", (), {}),
    OrderBookRow=type("OrderBookRow", (), {}),
)
_stub(
    "hummingbot.core.data_type.order_book_query_result",
    OrderBookQueryResult=type("OrderBookQueryResult", (), {}),
    ClientOrderBookQueryResult=type("ClientOrderBookQueryResult", (), {}),
)
_stub(
    "hummingbot.core.data_type.composite_order_book",
    CompositeOrderBook=type("CompositeOrderBook", (), {}),
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run(coro):
    """Run a coroutine in the default event loop."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_source(responses=None):
    """
    Build a LmexPerpetualUserStreamDataSource with a mock API factory.

    *responses* may be a list used as side_effect for execute_request so that
    successive calls return different values.  If None, execute_request always
    returns an empty list.
    """
    from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_user_stream_data_source import (
        LmexPerpetualUserStreamDataSource,
    )
    from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_auth import LmexPerpetualAuth

    auth = MagicMock(spec=LmexPerpetualAuth)

    connector = MagicMock()
    connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC-PERP")

    rest_assistant = AsyncMock()
    if responses is not None:
        rest_assistant.execute_request = AsyncMock(side_effect=responses)
    else:
        rest_assistant.execute_request = AsyncMock(return_value=[])

    factory = AsyncMock()
    factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)

    source = LmexPerpetualUserStreamDataSource(
        auth=auth,
        trading_pairs=["BTC-USDT"],
        connector=connector,
        api_factory=factory,
    )
    return source


# ---------------------------------------------------------------------------
# Test class 1 — exported event-key constants
# ---------------------------------------------------------------------------

class TestLmexPerpetualEventKeys(unittest.TestCase):
    """Tests that the four exported channel-key constants have the correct values."""

    def test_orders_event_key_value(self):
        """ORDERS_EVENT_KEY must equal 'lmex_perp.open_orders'."""
        from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_user_stream_data_source import (
            ORDERS_EVENT_KEY,
        )
        self.assertEqual(ORDERS_EVENT_KEY, "lmex_perp.open_orders")

    def test_trades_event_key_value(self):
        """TRADES_EVENT_KEY must equal 'lmex_perp.trade_history'."""
        from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_user_stream_data_source import (
            TRADES_EVENT_KEY,
        )
        self.assertEqual(TRADES_EVENT_KEY, "lmex_perp.trade_history")

    def test_positions_event_key_value(self):
        """POSITIONS_EVENT_KEY must equal 'lmex_perp.positions'."""
        from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_user_stream_data_source import (
            POSITIONS_EVENT_KEY,
        )
        self.assertEqual(POSITIONS_EVENT_KEY, "lmex_perp.positions")

    def test_wallet_event_key_value(self):
        """WALLET_EVENT_KEY must equal 'lmex_perp.wallet'."""
        from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_user_stream_data_source import (
            WALLET_EVENT_KEY,
        )
        self.assertEqual(WALLET_EVENT_KEY, "lmex_perp.wallet")

    def test_all_keys_are_strings(self):
        """All four exported event keys must be str instances."""
        from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_user_stream_data_source import (
            ORDERS_EVENT_KEY,
            POSITIONS_EVENT_KEY,
            TRADES_EVENT_KEY,
            WALLET_EVENT_KEY,
        )
        for key in (ORDERS_EVENT_KEY, TRADES_EVENT_KEY, POSITIONS_EVENT_KEY, WALLET_EVENT_KEY):
            with self.subTest(key=key):
                self.assertIsInstance(key, str)

    def test_all_keys_are_unique(self):
        """All four exported event keys must be distinct strings."""
        from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_user_stream_data_source import (
            ORDERS_EVENT_KEY,
            POSITIONS_EVENT_KEY,
            TRADES_EVENT_KEY,
            WALLET_EVENT_KEY,
        )
        keys = [ORDERS_EVENT_KEY, TRADES_EVENT_KEY, POSITIONS_EVENT_KEY, WALLET_EVENT_KEY]
        self.assertEqual(len(keys), len(set(keys)))


# ---------------------------------------------------------------------------
# Test class 2 — _poll_and_emit behaviour
# ---------------------------------------------------------------------------

class TestLmexPerpetualPollAndEmit(unittest.TestCase):
    """Tests for _poll_and_emit event emission rules."""

    # responses order: wallet, open_orders, trade_history, positions
    _WALLET_DATA = {"totalValue": "1000"}
    _ORDERS_DATA = [{"orderId": "1"}]
    _TRADES_DATA = [{"tradeId": "1"}]
    _POSITIONS_DATA = [{"symbol": "BTC-PERP"}]

    def _queue(self):
        """Return a fresh asyncio.Queue for output."""
        return asyncio.Queue()

    def test_wallet_event_always_emitted(self):
        """A wallet event is put on the queue regardless of other data."""
        source = _make_source(responses=[
            self._WALLET_DATA, [], [], [],
        ])
        q = self._queue()
        _run(source._poll_and_emit(q))
        items = [q.get_nowait() for _ in range(q.qsize())]
        channels = [i["channel"] for i in items]
        self.assertIn("lmex_perp.wallet", channels)

    def test_wallet_event_data_matches_response(self):
        """The wallet event's data field contains the raw wallet response."""
        source = _make_source(responses=[
            self._WALLET_DATA, [], [], [],
        ])
        q = self._queue()
        _run(source._poll_and_emit(q))
        items = [q.get_nowait() for _ in range(q.qsize())]
        wallet_events = [i for i in items if i["channel"] == "lmex_perp.wallet"]
        self.assertEqual(len(wallet_events), 1)
        self.assertEqual(wallet_events[0]["data"], self._WALLET_DATA)

    def test_orders_event_emitted_when_non_empty(self):
        """An open-orders event is emitted when the orders list is non-empty."""
        source = _make_source(responses=[
            self._WALLET_DATA, self._ORDERS_DATA, [], [],
        ])
        q = self._queue()
        _run(source._poll_and_emit(q))
        items = [q.get_nowait() for _ in range(q.qsize())]
        channels = [i["channel"] for i in items]
        self.assertIn("lmex_perp.open_orders", channels)

    def test_orders_event_not_emitted_when_empty(self):
        """No open-orders event is emitted when the response is an empty list."""
        source = _make_source(responses=[
            self._WALLET_DATA, [], [], [],
        ])
        q = self._queue()
        _run(source._poll_and_emit(q))
        items = [q.get_nowait() for _ in range(q.qsize())]
        channels = [i["channel"] for i in items]
        self.assertNotIn("lmex_perp.open_orders", channels)

    def test_trades_event_emitted_when_non_empty(self):
        """A trade-history event is emitted when the trades list is non-empty."""
        source = _make_source(responses=[
            self._WALLET_DATA, [], self._TRADES_DATA, [],
        ])
        q = self._queue()
        _run(source._poll_and_emit(q))
        items = [q.get_nowait() for _ in range(q.qsize())]
        channels = [i["channel"] for i in items]
        self.assertIn("lmex_perp.trade_history", channels)

    def test_trades_event_not_emitted_when_empty(self):
        """No trade-history event is emitted when the response is an empty list."""
        source = _make_source(responses=[
            self._WALLET_DATA, [], [], [],
        ])
        q = self._queue()
        _run(source._poll_and_emit(q))
        items = [q.get_nowait() for _ in range(q.qsize())]
        channels = [i["channel"] for i in items]
        self.assertNotIn("lmex_perp.trade_history", channels)

    def test_positions_event_emitted_when_non_empty(self):
        """A positions event is emitted when the positions list is non-empty."""
        source = _make_source(responses=[
            self._WALLET_DATA, [], [], self._POSITIONS_DATA,
        ])
        q = self._queue()
        _run(source._poll_and_emit(q))
        items = [q.get_nowait() for _ in range(q.qsize())]
        channels = [i["channel"] for i in items]
        self.assertIn("lmex_perp.positions", channels)

    def test_positions_event_not_emitted_when_empty(self):
        """No positions event is emitted when the response is an empty list."""
        source = _make_source(responses=[
            self._WALLET_DATA, [], [], [],
        ])
        q = self._queue()
        _run(source._poll_and_emit(q))
        items = [q.get_nowait() for _ in range(q.qsize())]
        channels = [i["channel"] for i in items]
        self.assertNotIn("lmex_perp.positions", channels)

    def test_all_four_events_emitted_when_all_non_empty(self):
        """All four channel events are emitted when every poll returns data."""
        source = _make_source(responses=[
            self._WALLET_DATA,
            self._ORDERS_DATA,
            self._TRADES_DATA,
            self._POSITIONS_DATA,
        ])
        q = self._queue()
        _run(source._poll_and_emit(q))
        items = [q.get_nowait() for _ in range(q.qsize())]
        channels = {i["channel"] for i in items}
        self.assertEqual(channels, {
            "lmex_perp.wallet",
            "lmex_perp.open_orders",
            "lmex_perp.trade_history",
            "lmex_perp.positions",
        })

    def test_wallet_exception_does_not_prevent_order_events(self):
        """A wallet poll error is caught; subsequent order events still fire."""
        from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_user_stream_data_source import (
            LmexPerpetualUserStreamDataSource,
        )
        from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_auth import LmexPerpetualAuth

        auth = MagicMock(spec=LmexPerpetualAuth)
        connector = MagicMock()
        connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC-PERP")

        rest_assistant = AsyncMock()
        # wallet raises, then orders returns data, trades empty, positions empty
        rest_assistant.execute_request = AsyncMock(
            side_effect=[Exception("wallet error"), self._ORDERS_DATA, [], []]
        )
        factory = AsyncMock()
        factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)

        source = LmexPerpetualUserStreamDataSource(
            auth=auth,
            trading_pairs=["BTC-USDT"],
            connector=connector,
            api_factory=factory,
        )
        q = self._queue()
        # Should not raise despite wallet error
        _run(source._poll_and_emit(q))
        items = [q.get_nowait() for _ in range(q.qsize())]
        channels = [i["channel"] for i in items]
        self.assertIn("lmex_perp.open_orders", channels)
        self.assertNotIn("lmex_perp.wallet", channels)

    def test_order_poll_exception_continues_to_trades(self):
        """An open-orders poll error is caught and trade-history polling continues."""
        from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_user_stream_data_source import (
            LmexPerpetualUserStreamDataSource,
        )
        from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_auth import LmexPerpetualAuth

        auth = MagicMock(spec=LmexPerpetualAuth)
        connector = MagicMock()
        connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC-PERP")

        rest_assistant = AsyncMock()
        # wallet ok, orders raises, trades returns data, positions empty
        rest_assistant.execute_request = AsyncMock(
            side_effect=[self._WALLET_DATA, Exception("orders error"), self._TRADES_DATA, []]
        )
        factory = AsyncMock()
        factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)

        source = LmexPerpetualUserStreamDataSource(
            auth=auth,
            trading_pairs=["BTC-USDT"],
            connector=connector,
            api_factory=factory,
        )
        q = self._queue()
        _run(source._poll_and_emit(q))
        items = [q.get_nowait() for _ in range(q.qsize())]
        channels = [i["channel"] for i in items]
        self.assertIn("lmex_perp.wallet", channels)
        self.assertIn("lmex_perp.trade_history", channels)
        self.assertNotIn("lmex_perp.open_orders", channels)

    def test_only_wallet_queued_when_all_lists_empty(self):
        """Exactly one event (wallet) is queued when all list responses are empty."""
        source = _make_source(responses=[
            self._WALLET_DATA, [], [], [],
        ])
        q = self._queue()
        _run(source._poll_and_emit(q))
        self.assertEqual(q.qsize(), 1)

    def test_orders_data_payload_is_correct(self):
        """The orders event's data field contains the raw orders list."""
        source = _make_source(responses=[
            self._WALLET_DATA, self._ORDERS_DATA, [], [],
        ])
        q = self._queue()
        _run(source._poll_and_emit(q))
        items = [q.get_nowait() for _ in range(q.qsize())]
        order_events = [i for i in items if i["channel"] == "lmex_perp.open_orders"]
        self.assertEqual(order_events[0]["data"], self._ORDERS_DATA)


# ---------------------------------------------------------------------------
# Test class 3 — WebSocket stubs raise NotImplementedError
# ---------------------------------------------------------------------------

class TestLmexPerpetualUserStreamWebSocketStubs(unittest.TestCase):
    """Tests that WS stubs raise NotImplementedError (REST-only connector)."""

    def setUp(self):
        """Create a shared source instance for stub tests."""
        self._source = _make_source()

    def test_connected_websocket_assistant_raises_not_implemented(self):
        """_connected_websocket_assistant must raise NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            _run(self._source._connected_websocket_assistant())

    def test_subscribe_channels_raises_not_implemented(self):
        """_subscribe_channels must raise NotImplementedError."""
        ws_mock = MagicMock()
        with self.assertRaises(NotImplementedError):
            _run(self._source._subscribe_channels(ws_mock))

    def test_connected_websocket_assistant_error_mentions_rest_polling(self):
        """The NotImplementedError from _connected_websocket_assistant mentions REST."""
        try:
            _run(self._source._connected_websocket_assistant())
        except NotImplementedError as exc:
            self.assertIn("REST", str(exc))

    def test_subscribe_channels_error_mentions_rest_polling(self):
        """The NotImplementedError from _subscribe_channels mentions REST."""
        ws_mock = MagicMock()
        try:
            _run(self._source._subscribe_channels(ws_mock))
        except NotImplementedError as exc:
            self.assertIn("REST", str(exc))


if __name__ == "__main__":
    unittest.main()
