"""
Unit tests for LmexAPIOrderBookDataSource.

These tests mock the REST assistant so no real HTTP requests are made.
They verify that:
  1. _order_book_snapshot converts LMEX L2 response to an OrderBookMessage.
  2. bids come from buyQuote, asks from sellQuote.
  3. timestamp is normalised from LMEX milliseconds → seconds.
  4. _parse_trade_message maps LMEX trade objects to OrderBookMessage TRADEs.
  5. _subscribe_channels and _connected_websocket_assistant raise NotImplementedError.
"""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.core.data_type.order_book_message import OrderBookMessageType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_TRADING_PAIR = "BTC-USD"
_SYMBOL = "BTC-USD"
_TS_MS = 1677663813822
_TS_S = _TS_MS / 1e3


def _make_connector(trading_pair=_TRADING_PAIR, symbol=_SYMBOL):
    connector = MagicMock()
    connector.exchange_symbol_associated_to_pair = AsyncMock(return_value=symbol)
    connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=trading_pair)
    connector.get_last_traded_prices = AsyncMock(return_value={trading_pair: 28000.0})
    return connector


def _make_api_factory(response):
    """Return a WebAssistantsFactory mock whose rest_assistant returns `response`."""
    rest_assistant = AsyncMock()
    rest_assistant.execute_request = AsyncMock(return_value=response)
    factory = AsyncMock()
    factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)
    return factory


def _make_source(connector, api_factory):
    """Import lazily so the module doesn't need to be importable at collection time."""
    from hummingbot.connector.exchange.lmex.lmex_api_order_book_data_source import (
        LmexAPIOrderBookDataSource,
    )

    return LmexAPIOrderBookDataSource(
        trading_pairs=[_TRADING_PAIR],
        connector=connector,
        api_factory=api_factory,
    )


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestLmexOrderBookSnapshot(unittest.TestCase):
    """Tests for _order_book_snapshot."""

    _SNAPSHOT_RESPONSE = {
        "symbol": _SYMBOL,
        "timestamp": _TS_MS,
        "buyQuote": [
            {"price": 27990.0, "size": 0.5},
            {"price": 27980.0, "size": 1.0},
        ],
        "sellQuote": [
            {"price": 28010.0, "size": 0.3},
            {"price": 28020.0, "size": 0.7},
        ],
        "depth": 50,
    }

    def setUp(self):
        self.connector = _make_connector()
        self.api_factory = _make_api_factory(self._SNAPSHOT_RESPONSE)

    def test_snapshot_message_type(self):
        source = _make_source(self.connector, self.api_factory)
        msg = _run(source._order_book_snapshot(_TRADING_PAIR))
        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)

    def test_snapshot_timestamp_converted_to_seconds(self):
        source = _make_source(self.connector, self.api_factory)
        msg = _run(source._order_book_snapshot(_TRADING_PAIR))
        self.assertAlmostEqual(_TS_S, msg.timestamp, places=0)

    def test_snapshot_bids_from_buy_quote(self):
        source = _make_source(self.connector, self.api_factory)
        msg = _run(source._order_book_snapshot(_TRADING_PAIR))
        # bids are [[price, size], ...]
        prices = [b[0] for b in msg.bids]
        self.assertIn(27990.0, prices)
        self.assertIn(27980.0, prices)

    def test_snapshot_asks_from_sell_quote(self):
        source = _make_source(self.connector, self.api_factory)
        msg = _run(source._order_book_snapshot(_TRADING_PAIR))
        prices = [a[0] for a in msg.asks]
        self.assertIn(28010.0, prices)
        self.assertIn(28020.0, prices)

    def test_snapshot_trading_pair_set(self):
        source = _make_source(self.connector, self.api_factory)
        msg = _run(source._order_book_snapshot(_TRADING_PAIR))
        self.assertEqual(_TRADING_PAIR, msg.content["trading_pair"])

    def test_snapshot_empty_orderbook(self):
        """An empty order book (no bids/asks) must not raise."""
        empty_response = {
            "symbol": _SYMBOL,
            "timestamp": _TS_MS,
            "buyQuote": [],
            "sellQuote": [],
        }
        source = _make_source(self.connector, _make_api_factory(empty_response))
        msg = _run(source._order_book_snapshot(_TRADING_PAIR))
        self.assertEqual([], msg.bids)
        self.assertEqual([], msg.asks)


class TestLmexParseTradeMessage(unittest.TestCase):
    """Tests for _parse_trade_message."""

    _TRADE = {
        "symbol": _SYMBOL,
        "side": "BUY",
        "price": 28000.0,
        "size": 0.1,
        "serialId": 123456789,
        "timestamp": _TS_MS,
    }

    def setUp(self):
        self.connector = _make_connector()
        self.api_factory = _make_api_factory({})
        self.source = _make_source(self.connector, self.api_factory)
        self.queue = asyncio.Queue()

    def test_trade_message_type(self):
        _run(self.source._parse_trade_message(self._TRADE, self.queue))
        msg = self.queue.get_nowait()
        self.assertEqual(OrderBookMessageType.TRADE, msg.type)

    def test_trade_price_and_amount(self):
        _run(self.source._parse_trade_message(self._TRADE, self.queue))
        msg = self.queue.get_nowait()
        self.assertEqual("28000.0", msg.content["price"])
        self.assertEqual("0.1", msg.content["amount"])

    def test_sell_trade_type(self):
        sell_trade = dict(self._TRADE, side="SELL")
        _run(self.source._parse_trade_message(sell_trade, self.queue))
        msg = self.queue.get_nowait()
        from hummingbot.core.data_type.common import TradeType
        self.assertEqual(float(TradeType.SELL.value), msg.content["trade_type"])

    def test_buy_trade_type(self):
        _run(self.source._parse_trade_message(self._TRADE, self.queue))
        msg = self.queue.get_nowait()
        from hummingbot.core.data_type.common import TradeType
        self.assertEqual(float(TradeType.BUY.value), msg.content["trade_type"])

    def test_trade_id_from_serial_id(self):
        _run(self.source._parse_trade_message(self._TRADE, self.queue))
        msg = self.queue.get_nowait()
        self.assertEqual(123456789, msg.content["trade_id"])

    def test_trade_timestamp_in_seconds(self):
        _run(self.source._parse_trade_message(self._TRADE, self.queue))
        msg = self.queue.get_nowait()
        self.assertAlmostEqual(_TS_S, msg.timestamp, places=0)


class TestLmexWebSocketNotImplemented(unittest.TestCase):
    """_connected_websocket_assistant and _subscribe_channels must raise NotImplementedError."""

    def setUp(self):
        self.source = _make_source(_make_connector(), _make_api_factory({}))

    def test_connected_websocket_assistant_raises(self):
        with self.assertRaises(NotImplementedError):
            _run(self.source._connected_websocket_assistant())

    def test_subscribe_channels_raises(self):
        ws_mock = MagicMock()
        with self.assertRaises(NotImplementedError):
            _run(self.source._subscribe_channels(ws_mock))


if __name__ == "__main__":
    unittest.main()
