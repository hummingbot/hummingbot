"""
Unit tests for LmexPerpetualAPIOrderBookDataSource.

Covers:
  - _order_book_snapshot: message type, timestamp conversion, bid/ask parsing,
    trading_pair field, empty book, update_id derivation
  - get_funding_info: funding_rate, mark_price, trading_pair, defaults
  - _find_symbol_summary: list match, list fallback, empty list, dict passthrough
  - _connected_websocket_assistant / _subscribe_channels: NotImplementedError stubs

All tests are pure unit tests using stdlib + unittest + unittest.mock.
No live network calls are made.
"""

import asyncio
import sys
import types
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Cython stub shim — order_book and related modules are compiled extensions
# that are not available without a build step.  Stub them before any source
# module is imported so the import chain resolves cleanly.
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
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run a coroutine in the default event loop."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_connector():
    """Build a minimal mock connector with async symbol-lookup methods."""
    c = MagicMock()
    c.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC-PERP")
    c.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="BTC-USDT")
    c.get_last_traded_prices = AsyncMock(return_value={"BTC-USDT": 50000.0})
    return c


def _make_api_factory(response):
    """Build a mock API factory whose REST assistant returns *response*."""
    rest = AsyncMock()
    rest.execute_request = AsyncMock(return_value=response)
    factory = AsyncMock()
    factory.get_rest_assistant = AsyncMock(return_value=rest)
    return factory


def _make_source(connector, api_factory):
    """
    Instantiate a concrete subclass of LmexPerpetualAPIOrderBookDataSource.

    The base class hierarchy may declare abstract methods
    (subscribe_to_trading_pair, unsubscribe_from_trading_pair) that the LMEX
    connector does not implement because it is REST-only.  We satisfy the ABC
    contract with no-op stubs so the class can be instantiated in tests.
    """
    from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_api_order_book_data_source import (
        LmexPerpetualAPIOrderBookDataSource,
    )

    class _Concrete(LmexPerpetualAPIOrderBookDataSource):
        async def subscribe_to_trading_pair(self, trading_pair: str):
            pass

        async def unsubscribe_from_trading_pair(self, trading_pair: str):
            pass

    return _Concrete(
        trading_pairs=["BTC-USDT"],
        connector=connector,
        api_factory=api_factory,
    )


# ---------------------------------------------------------------------------
# Test class 1 — snapshot structure
# ---------------------------------------------------------------------------

class TestLmexPerpetualOrderBookSnapshot(unittest.TestCase):
    """Tests for _order_book_snapshot return value correctness."""

    def _snapshot_response(self, timestamp_ms, bids, asks):
        """Build a synthetic REST response dict."""
        return {
            "timestamp": timestamp_ms,
            "buyQuote": [{"price": p, "size": s} for p, s in bids],
            "sellQuote": [{"price": p, "size": s} for p, s in asks],
        }

    def test_message_type_is_snapshot(self):
        """Returned message must have type SNAPSHOT."""
        from hummingbot.core.data_type.order_book_message import OrderBookMessageType
        response = self._snapshot_response(1_700_000_000_000, [(50000, 1)], [(50001, 1)])
        source = _make_source(_make_connector(), _make_api_factory(response))
        msg = _run(source._order_book_snapshot("BTC-USDT"))
        self.assertEqual(msg.type, OrderBookMessageType.SNAPSHOT)

    def test_timestamp_converted_from_milliseconds_to_seconds(self):
        """Snapshot timestamp field is milliseconds divided by 1000."""
        ts_ms = 1_700_000_000_000
        response = self._snapshot_response(ts_ms, [], [])
        source = _make_source(_make_connector(), _make_api_factory(response))
        msg = _run(source._order_book_snapshot("BTC-USDT"))
        self.assertAlmostEqual(msg.timestamp, ts_ms * 1e-3, places=3)

    def test_bids_parsed_from_buy_quote(self):
        """Bids list is built from the buyQuote entries as [price, size] pairs."""
        response = self._snapshot_response(
            1_700_000_000_000,
            [(50000, 2), (49999, 1)],
            [],
        )
        source = _make_source(_make_connector(), _make_api_factory(response))
        msg = _run(source._order_book_snapshot("BTC-USDT"))
        self.assertEqual(msg.content["bids"], [[50000, 2], [49999, 1]])

    def test_asks_parsed_from_sell_quote(self):
        """Asks list is built from the sellQuote entries as [price, size] pairs."""
        response = self._snapshot_response(
            1_700_000_000_000,
            [],
            [(50001, 3), (50002, 1)],
        )
        source = _make_source(_make_connector(), _make_api_factory(response))
        msg = _run(source._order_book_snapshot("BTC-USDT"))
        self.assertEqual(msg.content["asks"], [[50001, 3], [50002, 1]])

    def test_trading_pair_set_in_content(self):
        """The trading_pair key in the message content must match the requested pair."""
        response = self._snapshot_response(1_700_000_000_000, [], [])
        source = _make_source(_make_connector(), _make_api_factory(response))
        msg = _run(source._order_book_snapshot("BTC-USDT"))
        self.assertEqual(msg.content["trading_pair"], "BTC-USDT")

    def test_empty_order_book_returns_empty_lists(self):
        """A response with no quotes produces empty bids and asks lists."""
        response = self._snapshot_response(1_700_000_000_000, [], [])
        source = _make_source(_make_connector(), _make_api_factory(response))
        msg = _run(source._order_book_snapshot("BTC-USDT"))
        self.assertEqual(msg.content["bids"], [])
        self.assertEqual(msg.content["asks"], [])

    def test_update_id_derived_from_timestamp_ms(self):
        """update_id is the integer value of the millisecond timestamp."""
        ts_ms = 1_700_000_000_123
        response = self._snapshot_response(ts_ms, [], [])
        source = _make_source(_make_connector(), _make_api_factory(response))
        msg = _run(source._order_book_snapshot("BTC-USDT"))
        self.assertEqual(msg.content["update_id"], ts_ms)

    def test_missing_timestamp_falls_back_to_time_dot_time(self):
        """When timestamp is absent the code falls back to time.time()*1000."""
        response = {"buyQuote": [], "sellQuote": []}  # no timestamp key
        import time as _time
        fake_now = 1_700_000_000.0
        source = _make_source(_make_connector(), _make_api_factory(response))
        with patch("hummingbot.connector.derivative.lmex_perpetual"
                   ".lmex_perpetual_api_order_book_data_source.time") as mock_time:
            mock_time.time.return_value = fake_now
            msg = _run(source._order_book_snapshot("BTC-USDT"))
        self.assertAlmostEqual(msg.timestamp, fake_now, places=2)

    def test_multiple_bids_and_asks_all_included(self):
        """All bid and ask entries from a multi-level book are included."""
        bids = [(50000 - i * 10, i + 1) for i in range(5)]
        asks = [(50010 + i * 10, i + 1) for i in range(5)]
        response = self._snapshot_response(1_700_000_000_000, bids, asks)
        source = _make_source(_make_connector(), _make_api_factory(response))
        msg = _run(source._order_book_snapshot("BTC-USDT"))
        self.assertEqual(len(msg.content["bids"]), 5)
        self.assertEqual(len(msg.content["asks"]), 5)

    def test_request_passes_trading_pair_to_connector(self):
        """_request_order_book_snapshot asks the connector to resolve the symbol."""
        connector = _make_connector()
        response = self._snapshot_response(1_700_000_000_000, [], [])
        source = _make_source(connector, _make_api_factory(response))
        _run(source._order_book_snapshot("BTC-USDT"))
        connector.exchange_symbol_associated_to_pair.assert_awaited_with(
            trading_pair="BTC-USDT"
        )


# ---------------------------------------------------------------------------
# Test class 2 — get_funding_info
# ---------------------------------------------------------------------------

class TestLmexPerpetualFundingInfo(unittest.TestCase):
    """Tests for get_funding_info return value correctness."""

    def _summary_response(self, symbol="BTC-PERP", funding_rate="0.0001",
                          last="50000", funding_interval_minutes=480):
        """Build a synthetic market-summary REST response (list form)."""
        return [
            {
                "symbol": symbol,
                "fundingRate": funding_rate,
                "last": last,
                "fundingIntervalMinutes": funding_interval_minutes,
            }
        ]

    def test_funding_rate_set_correctly(self):
        """FundingInfo.rate must equal the fundingRate field from the response."""
        response = self._summary_response(funding_rate="0.0001")
        source = _make_source(_make_connector(), _make_api_factory(response))
        info = _run(source.get_funding_info("BTC-USDT"))
        self.assertEqual(info.rate, Decimal("0.0001"))

    def test_mark_price_set_from_last(self):
        """FundingInfo.mark_price must equal the last price from the response."""
        response = self._summary_response(last="50000")
        source = _make_source(_make_connector(), _make_api_factory(response))
        info = _run(source.get_funding_info("BTC-USDT"))
        self.assertEqual(info.mark_price, Decimal("50000"))

    def test_index_price_equals_mark_price(self):
        """FundingInfo.index_price is set to the same value as mark_price."""
        response = self._summary_response(last="48000")
        source = _make_source(_make_connector(), _make_api_factory(response))
        info = _run(source.get_funding_info("BTC-USDT"))
        self.assertEqual(info.index_price, info.mark_price)

    def test_trading_pair_set_on_funding_info(self):
        """FundingInfo.trading_pair reflects the pair requested."""
        response = self._summary_response()
        source = _make_source(_make_connector(), _make_api_factory(response))
        info = _run(source.get_funding_info("BTC-USDT"))
        self.assertEqual(info.trading_pair, "BTC-USDT")

    def test_missing_funding_rate_defaults_to_zero(self):
        """When fundingRate is absent the rate defaults to Decimal('0')."""
        response = [{"symbol": "BTC-PERP", "last": "50000"}]
        source = _make_source(_make_connector(), _make_api_factory(response))
        info = _run(source.get_funding_info("BTC-USDT"))
        self.assertEqual(info.rate, Decimal("0"))

    def test_missing_last_defaults_mark_price_to_zero(self):
        """When last is absent the mark_price defaults to Decimal('0')."""
        response = [{"symbol": "BTC-PERP", "fundingRate": "0.001"}]
        source = _make_source(_make_connector(), _make_api_factory(response))
        info = _run(source.get_funding_info("BTC-USDT"))
        self.assertEqual(info.mark_price, Decimal("0"))

    def test_funding_interval_minutes_default_480(self):
        """A missing fundingIntervalMinutes causes next_funding to be 480 min ahead."""
        response = [{"symbol": "BTC-PERP", "last": "50000", "fundingRate": "0"}]
        import time as _time
        fake_now = 0.0  # epoch start for easy arithmetic
        source = _make_source(_make_connector(), _make_api_factory(response))
        with patch("hummingbot.connector.derivative.lmex_perpetual"
                   ".lmex_perpetual_api_order_book_data_source.time") as mock_time:
            mock_time.time.return_value = fake_now
            info = _run(source.get_funding_info("BTC-USDT"))
        expected_interval = 480 * 60
        self.assertEqual(info.next_funding_utc_timestamp, expected_interval)

    def test_custom_funding_interval_minutes_used(self):
        """When fundingIntervalMinutes is present it overrides the 480-min default."""
        response = self._summary_response(funding_interval_minutes=60)
        import time as _time
        fake_now = 0.0
        source = _make_source(_make_connector(), _make_api_factory(response))
        with patch("hummingbot.connector.derivative.lmex_perpetual"
                   ".lmex_perpetual_api_order_book_data_source.time") as mock_time:
            mock_time.time.return_value = fake_now
            info = _run(source.get_funding_info("BTC-USDT"))
        expected_interval = 60 * 60
        self.assertEqual(info.next_funding_utc_timestamp, expected_interval)

    def test_connector_symbol_lookup_called(self):
        """get_funding_info must resolve the exchange symbol via the connector."""
        connector = _make_connector()
        response = self._summary_response()
        source = _make_source(connector, _make_api_factory(response))
        _run(source.get_funding_info("BTC-USDT"))
        connector.exchange_symbol_associated_to_pair.assert_awaited_with(
            trading_pair="BTC-USDT"
        )

    def test_find_symbol_summary_selects_correct_entry(self):
        """get_funding_info picks the entry whose symbol matches the exchange symbol."""
        connector = _make_connector()
        connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="ETH-PERP")
        response = [
            {"symbol": "BTC-PERP", "last": "50000", "fundingRate": "0.0001"},
            {"symbol": "ETH-PERP", "last": "3000", "fundingRate": "0.0002"},
        ]
        source = _make_source(connector, _make_api_factory(response))
        info = _run(source.get_funding_info("ETH-USDT"))
        self.assertEqual(info.mark_price, Decimal("3000"))
        self.assertEqual(info.rate, Decimal("0.0002"))


# ---------------------------------------------------------------------------
# Test class 3 — _find_symbol_summary
# ---------------------------------------------------------------------------

class TestLmexPerpetualFindSymbolSummary(unittest.TestCase):
    """Tests for the _find_symbol_summary static helper method."""

    def setUp(self):
        """Import the static method once for all tests in this class."""
        from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_api_order_book_data_source import (
            LmexPerpetualAPIOrderBookDataSource,
        )
        self._find = LmexPerpetualAPIOrderBookDataSource._find_symbol_summary

    def test_finds_matching_symbol_in_list(self):
        """Returns the entry whose symbol key equals the requested symbol."""
        data = [
            {"symbol": "BTC-PERP", "val": 1},
            {"symbol": "ETH-PERP", "val": 2},
        ]
        result = self._find(data, "ETH-PERP")
        self.assertEqual(result["val"], 2)

    def test_falls_back_to_first_item_when_no_match(self):
        """Returns the first item when no entry's symbol matches."""
        data = [
            {"symbol": "BTC-PERP", "val": 99},
            {"symbol": "LTC-PERP", "val": 42},
        ]
        result = self._find(data, "UNKNOWN-PERP")
        self.assertEqual(result["val"], 99)

    def test_returns_empty_dict_for_empty_list(self):
        """Returns an empty dict when the response list is empty."""
        result = self._find([], "BTC-PERP")
        self.assertEqual(result, {})

    def test_returns_dict_as_is_when_response_is_dict(self):
        """Returns the dict unchanged when the response is already a dict."""
        data = {"symbol": "BTC-PERP", "last": "50000"}
        result = self._find(data, "BTC-PERP")
        self.assertIs(result, data)

    def test_dict_response_not_filtered_by_symbol(self):
        """A dict whose symbol does not match is still returned as-is."""
        data = {"symbol": "ETH-PERP", "last": "3000"}
        result = self._find(data, "BTC-PERP")
        self.assertIs(result, data)

    def test_single_item_list_matched(self):
        """A single-item list whose symbol matches is returned correctly."""
        data = [{"symbol": "BTC-PERP", "last": "55000"}]
        result = self._find(data, "BTC-PERP")
        self.assertEqual(result["last"], "55000")

    def test_single_item_list_fallback(self):
        """A single-item list with no match falls back to that one item."""
        data = [{"symbol": "BTC-PERP", "last": "55000"}]
        result = self._find(data, "MISSING")
        self.assertEqual(result["last"], "55000")


# ---------------------------------------------------------------------------
# Test class 4 — WebSocket stubs raise NotImplementedError
# ---------------------------------------------------------------------------

class TestLmexPerpetualOrderBookWebSocketStubs(unittest.TestCase):
    """Tests that WS stubs raise NotImplementedError (REST-only connector)."""

    def setUp(self):
        """Create a source instance shared by all stub tests."""
        self._source = _make_source(_make_connector(), _make_api_factory({}))

    def test_connected_websocket_assistant_raises_not_implemented(self):
        """_connected_websocket_assistant must raise NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            _run(self._source._connected_websocket_assistant())

    def test_subscribe_channels_raises_not_implemented(self):
        """_subscribe_channels must raise NotImplementedError."""
        ws_mock = MagicMock()
        with self.assertRaises(NotImplementedError):
            _run(self._source._subscribe_channels(ws_mock))

    def test_connected_websocket_assistant_error_message_mentions_lmex(self):
        """The NotImplementedError message references LMEX."""
        try:
            _run(self._source._connected_websocket_assistant())
        except NotImplementedError as exc:
            self.assertIn("LMEX", str(exc))

    def test_subscribe_channels_error_message_mentions_lmex(self):
        """The NotImplementedError message from _subscribe_channels references LMEX."""
        ws_mock = MagicMock()
        try:
            _run(self._source._subscribe_channels(ws_mock))
        except NotImplementedError as exc:
            self.assertIn("LMEX", str(exc))


if __name__ == "__main__":
    unittest.main()
