"""
Unit tests for LmexPerpetualDerivative.

Tests cover all pure-Python logic that does not require a running event loop,
network access, or compiled Cython extensions.  The base class
``PerpetualDerivativePyBase.__init__`` is patched out so the full
Hummingbot runtime is never initialised.

Covered:
  - _order_state_from_status   — all 13 status codes + None + unknown
  - _process_balance_message   — set/update/clear/stale-removal
  - _create_order_update_from_data — state mapping, timestamp conversion,
                                     client/exchange order id, fallbacks
  - _initialize_trading_pair_symbols_from_exchange_info — PERP mapping,
                                     inactive skipped, non-PERP skipped
  - _amount_to_contracts / _contracts_to_amount — math, rounding, defaults
  - _process_position_data     — LONG/SHORT set, zero removes, bad symbol
  - _create_trade_update_from_fill — price, amount, trade_id, timestamp
  - _set_trading_pair_leverage — success, mismatch, exception
  - _execute_set_position_mode_for_pairs — ONEWAY ok, other rejected
  - _process_order_message / _process_trade_message — routing, unknown id
  - Properties / error classifiers
"""
import asyncio
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.core.data_type.common import OrderType, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState

_TRADING_PAIR = "BTC-USDT"
_EX_SYMBOL    = "BTC-PERP"
_TS_MS        = 1_677_663_813_822
_TS_S         = _TS_MS / 1e3


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def _make_derivative():
    from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_derivative import (
        LmexPerpetualDerivative,
    )

    with patch.object(LmexPerpetualDerivative.__bases__[0], "__init__", return_value=None):
        d = LmexPerpetualDerivative.__new__(LmexPerpetualDerivative)

    d._lmex_perpetual_api_key    = "test_api_key"
    d._lmex_perpetual_secret_key = "test_secret_key"
    d._domain         = "lmex_perpetual"
    d._trading_pairs  = [_TRADING_PAIR]
    d._trading_required = True
    d._position_mode  = None
    d._account_balances           = {}
    d._account_available_balances = {}
    d._contract_sizes             = {}
    d.current_timestamp           = 1_677_663_813.822

    # Mocks for framework collaborators
    perp = MagicMock()
    perp.position_key       = MagicMock(return_value="BTC-USDT_LONG")
    perp.set_position       = MagicMock()
    perp.remove_position    = MagicMock()
    d._perpetual_trading = perp

    tracker = MagicMock()
    tracker.all_updatable_orders = {}
    tracker.all_fillable_orders  = {}
    tracker.process_order_update = MagicMock()
    tracker.process_trade_update = MagicMock()
    d._order_tracker = tracker

    d._set_trading_pair_symbol_map = MagicMock()
    d.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=_TRADING_PAIR)
    d.exchange_symbol_associated_to_pair         = AsyncMock(return_value=_EX_SYMBOL)
    d.logger = MagicMock(return_value=MagicMock())
    return d


def _make_in_flight_order(client_order_id="HBOT-001",
                           exchange_order_id="EX-UUID-1234",
                           trading_pair=_TRADING_PAIR,
                           current_state=OrderState.OPEN,
                           quote_asset="USDT"):
    o = MagicMock()
    o.client_order_id   = client_order_id
    o.exchange_order_id = exchange_order_id
    o.trading_pair      = trading_pair
    o.current_state     = current_state
    o.quote_asset       = quote_asset
    return o


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# 1. Order state mapping
# ---------------------------------------------------------------------------

class TestLmexPerpetualOrderStateMapping(unittest.TestCase):

    def setUp(self):
        self.d = _make_derivative()

    def test_status_2_is_open(self):
        """Status 2 (INSERTED) maps to OPEN."""
        self.assertEqual(OrderState.OPEN, self.d._order_state_from_status(2))

    def test_status_4_is_filled(self):
        """Status 4 (FULLY_TRANSACTED) maps to FILLED."""
        self.assertEqual(OrderState.FILLED, self.d._order_state_from_status(4))

    def test_status_5_is_partially_filled(self):
        """Status 5 (PARTIALLY_TRANSACTED) maps to PARTIALLY_FILLED."""
        self.assertEqual(OrderState.PARTIALLY_FILLED, self.d._order_state_from_status(5))

    def test_status_6_is_canceled(self):
        """Status 6 (CANCELLED) maps to CANCELED."""
        self.assertEqual(OrderState.CANCELED, self.d._order_state_from_status(6))

    def test_status_7_is_canceled(self):
        """Status 7 (REFUNDED) maps to CANCELED."""
        self.assertEqual(OrderState.CANCELED, self.d._order_state_from_status(7))

    def test_status_8_is_failed(self):
        """Status 8 (INSUFFICIENT_BALANCE) maps to FAILED."""
        self.assertEqual(OrderState.FAILED, self.d._order_state_from_status(8))

    def test_status_9_is_open(self):
        """Status 9 (TRIGGER_INSERTED) maps to OPEN."""
        self.assertEqual(OrderState.OPEN, self.d._order_state_from_status(9))

    def test_status_10_is_open(self):
        """Status 10 (TRIGGER_ACTIVATED) maps to OPEN."""
        self.assertEqual(OrderState.OPEN, self.d._order_state_from_status(10))

    def test_status_15_is_failed(self):
        """Status 15 (REJECTED) maps to FAILED."""
        self.assertEqual(OrderState.FAILED, self.d._order_state_from_status(15))

    def test_status_65_is_open(self):
        """Status 65 (ACTIVE) maps to OPEN."""
        self.assertEqual(OrderState.OPEN, self.d._order_state_from_status(65))

    def test_status_85_is_open(self):
        """Status 85 (PROCESSING) maps to OPEN."""
        self.assertEqual(OrderState.OPEN, self.d._order_state_from_status(85))

    def test_status_88_is_open(self):
        """Status 88 (INACTIVE) maps to OPEN."""
        self.assertEqual(OrderState.OPEN, self.d._order_state_from_status(88))

    def test_none_returns_none(self):
        """None status returns None (caller falls back to current state)."""
        self.assertIsNone(self.d._order_state_from_status(None))

    def test_unknown_status_returns_none(self):
        """An unrecognised status code returns None."""
        self.assertIsNone(self.d._order_state_from_status(999))

    def test_filled_is_not_open(self):
        """Status 4 (FILLED) must not map to OPEN."""
        self.assertNotEqual(OrderState.OPEN, self.d._order_state_from_status(4))


# ---------------------------------------------------------------------------
# 2. Balance processing
# ---------------------------------------------------------------------------

class TestLmexPerpetualBalanceProcessing(unittest.TestCase):

    def setUp(self):
        self.d = _make_derivative()

    def test_sets_total_balance(self):
        """Total balance is set from the wallet entry."""
        self.d._process_balance_message([{"currency": "USDT", "total": "1000.50", "available": "900.0"}])
        self.assertEqual(Decimal("1000.50"), self.d._account_balances["USDT"])

    def test_sets_available_balance(self):
        """Available balance is set from the wallet entry."""
        self.d._process_balance_message([{"currency": "USDT", "total": "1000.50", "available": "900.0"}])
        self.assertEqual(Decimal("900.0"), self.d._account_available_balances["USDT"])

    def test_multiple_currencies(self):
        """Multiple currencies are all stored correctly."""
        self.d._process_balance_message([
            {"currency": "USDT", "total": "1000", "available": "900"},
            {"currency": "BTC",  "total": "0.5",  "available": "0.5"},
        ])
        self.assertIn("USDT", self.d._account_balances)
        self.assertIn("BTC",  self.d._account_balances)
        self.assertEqual(Decimal("0.5"), self.d._account_balances["BTC"])

    def test_stale_asset_removed(self):
        """Assets absent from the new response are removed from local state."""
        self.d._account_balances["ETH"]           = Decimal("2")
        self.d._account_available_balances["ETH"] = Decimal("2")
        self.d._process_balance_message([{"currency": "USDT", "total": "100", "available": "100"}])
        self.assertNotIn("ETH", self.d._account_balances)
        self.assertNotIn("ETH", self.d._account_available_balances)

    def test_empty_wallet_clears_balances(self):
        """An empty wallet response clears all previously stored balances."""
        self.d._account_balances["USDT"]           = Decimal("100")
        self.d._account_available_balances["USDT"] = Decimal("100")
        self.d._process_balance_message([])
        self.assertEqual({}, self.d._account_balances)

    def test_single_dict_input_accepted(self):
        """A single dict (not a list) is handled without raising."""
        self.d._process_balance_message({"currency": "USDT", "total": "50", "available": "50"})
        self.assertIn("USDT", self.d._account_balances)

    def test_missing_currency_defaults_to_usdt(self):
        """An entry missing 'currency' defaults the key to 'USDT'."""
        self.d._process_balance_message([{"total": "10", "available": "10"}])
        self.assertIn("USDT", self.d._account_balances)


# ---------------------------------------------------------------------------
# 3. OrderUpdate construction
# ---------------------------------------------------------------------------

class TestLmexPerpetualOrderUpdate(unittest.TestCase):

    def setUp(self):
        self.d = _make_derivative()

    def _make_data(self, status=4, ts=_TS_MS, cl_id="HBOT-001", ex_id="EX-UUID"):
        return {"status": status, "timestamp": ts, "clOrderID": cl_id, "orderID": ex_id}

    def test_filled_status_maps_to_filled(self):
        """Status 4 produces OrderState.FILLED."""
        upd = self.d._create_order_update_from_data(self._make_data(status=4), _make_in_flight_order())
        self.assertEqual(OrderState.FILLED, upd.new_state)

    def test_canceled_status_maps_to_canceled(self):
        """Status 6 produces OrderState.CANCELED."""
        upd = self.d._create_order_update_from_data(self._make_data(status=6), _make_in_flight_order())
        self.assertEqual(OrderState.CANCELED, upd.new_state)

    def test_failed_status_maps_to_failed(self):
        """Status 15 produces OrderState.FAILED."""
        upd = self.d._create_order_update_from_data(self._make_data(status=15), _make_in_flight_order())
        self.assertEqual(OrderState.FAILED, upd.new_state)

    def test_open_status_maps_to_open(self):
        """Status 2 produces OrderState.OPEN."""
        upd = self.d._create_order_update_from_data(self._make_data(status=2), _make_in_flight_order())
        self.assertEqual(OrderState.OPEN, upd.new_state)

    def test_unknown_status_falls_back_to_current_state(self):
        """Unknown status uses the order's current_state as fallback."""
        order = _make_in_flight_order(current_state=OrderState.OPEN)
        upd = self.d._create_order_update_from_data(self._make_data(status=999), order)
        self.assertEqual(OrderState.OPEN, upd.new_state)

    def test_millisecond_timestamp_divided_by_1000(self):
        """A millisecond timestamp (e.g. 1677663813822) is divided by 1e3."""
        upd = self.d._create_order_update_from_data(self._make_data(ts=_TS_MS), _make_in_flight_order())
        self.assertAlmostEqual(_TS_S, upd.update_timestamp, places=0)

    def test_bad_timestamp_falls_back_to_current_timestamp(self):
        """A non-numeric timestamp falls back to connector's current_timestamp."""
        data = {"status": 4, "timestamp": "not-a-number", "clOrderID": "HBOT-001", "orderID": "EX"}
        upd = self.d._create_order_update_from_data(data, _make_in_flight_order())
        self.assertEqual(self.d.current_timestamp, upd.update_timestamp)

    def test_client_order_id_echoed_from_clOrderID(self):
        """clOrderID in the response is used as client_order_id."""
        upd = self.d._create_order_update_from_data(self._make_data(cl_id="HBOT-XYZ"), _make_in_flight_order())
        self.assertEqual("HBOT-XYZ", upd.client_order_id)

    def test_client_order_id_falls_back_to_order(self):
        """Missing clOrderID falls back to the in-flight order's client_order_id."""
        data = {"status": 4, "timestamp": _TS_MS, "orderID": "EX"}
        order = _make_in_flight_order(client_order_id="HBOT-FALLBACK")
        upd = self.d._create_order_update_from_data(data, order)
        self.assertEqual("HBOT-FALLBACK", upd.client_order_id)

    def test_exchange_order_id_set_as_string(self):
        """exchange_order_id is stored as a string."""
        upd = self.d._create_order_update_from_data(self._make_data(ex_id="UUID-9999"), _make_in_flight_order())
        self.assertEqual("UUID-9999", upd.exchange_order_id)

    def test_trading_pair_set_from_order(self):
        """trading_pair is taken from the in-flight order."""
        order = _make_in_flight_order(trading_pair="ETH-USDT")
        upd = self.d._create_order_update_from_data(self._make_data(), order)
        self.assertEqual("ETH-USDT", upd.trading_pair)


# ---------------------------------------------------------------------------
# 4. Symbol mapping
# ---------------------------------------------------------------------------

class TestLmexPerpetualSymbolMapping(unittest.TestCase):

    def setUp(self):
        self.d = _make_derivative()

    def test_btc_perp_maps_to_btc_usdt(self):
        """BTC-PERP maps to BTC-USDT."""
        self.d._initialize_trading_pair_symbols_from_exchange_info(
            [{"symbol": "BTC-PERP", "active": True}]
        )
        call_args = self.d._set_trading_pair_symbol_map.call_args[0][0]
        self.assertEqual("BTC-USDT", call_args["BTC-PERP"])

    def test_eth_perp_maps_to_eth_usdt(self):
        """ETH-PERP maps to ETH-USDT."""
        self.d._initialize_trading_pair_symbols_from_exchange_info(
            [{"symbol": "ETH-PERP", "active": True}]
        )
        call_args = self.d._set_trading_pair_symbol_map.call_args[0][0]
        self.assertEqual("ETH-USDT", call_args["ETH-PERP"])

    def test_multiple_perp_pairs(self):
        """Multiple PERP pairs are all mapped."""
        self.d._initialize_trading_pair_symbols_from_exchange_info([
            {"symbol": "BTC-PERP", "active": True},
            {"symbol": "SOL-PERP", "active": True},
        ])
        m = self.d._set_trading_pair_symbol_map.call_args[0][0]
        self.assertIn("BTC-PERP", m)
        self.assertIn("SOL-PERP", m)

    def test_inactive_pair_skipped(self):
        """Inactive markets are excluded from the mapping."""
        self.d._initialize_trading_pair_symbols_from_exchange_info(
            [{"symbol": "BTC-PERP", "active": False}]
        )
        m = self.d._set_trading_pair_symbol_map.call_args[0][0]
        self.assertNotIn("BTC-PERP", m)

    def test_non_perp_symbol_skipped(self):
        """Spot or quarterly symbols (no -PERP suffix) are excluded."""
        self.d._initialize_trading_pair_symbols_from_exchange_info(
            [{"symbol": "BTC-USD", "active": True}]
        )
        m = self.d._set_trading_pair_symbol_map.call_args[0][0]
        self.assertNotIn("BTC-USD", m)

    def test_empty_exchange_info(self):
        """Empty exchange info produces an empty mapping without error."""
        self.d._initialize_trading_pair_symbols_from_exchange_info([])
        m = self.d._set_trading_pair_symbol_map.call_args[0][0]
        self.assertEqual(0, len(m))

    def test_single_dict_input(self):
        """A single dict (not list) is handled correctly."""
        self.d._initialize_trading_pair_symbols_from_exchange_info(
            {"symbol": "BTC-PERP", "active": True}
        )
        m = self.d._set_trading_pair_symbol_map.call_args[0][0]
        self.assertIn("BTC-PERP", m)


# ---------------------------------------------------------------------------
# 5. Contract sizing
# ---------------------------------------------------------------------------

class TestLmexPerpetualContractSizing(unittest.TestCase):

    def setUp(self):
        self.d = _make_derivative()

    def test_amount_to_contracts_basic(self):
        """1.0 BTC with contractSize=0.001 = 1000 contracts."""
        self.d._contract_sizes[_TRADING_PAIR] = Decimal("0.001")
        self.assertEqual(1000, self.d._amount_to_contracts(_TRADING_PAIR, Decimal("1.0")))

    def test_amount_to_contracts_rounds_down(self):
        """Fractional contracts are rounded down (floor division)."""
        self.d._contract_sizes[_TRADING_PAIR] = Decimal("0.001")
        self.assertEqual(1, self.d._amount_to_contracts(_TRADING_PAIR, Decimal("0.0019")))

    def test_amount_to_contracts_zero(self):
        """Zero amount produces zero contracts."""
        self.d._contract_sizes[_TRADING_PAIR] = Decimal("0.001")
        self.assertEqual(0, self.d._amount_to_contracts(_TRADING_PAIR, Decimal("0")))

    def test_amount_to_contracts_missing_key_defaults_to_1(self):
        """Missing contract size defaults to 1 (1 contract = 1 unit)."""
        self.assertEqual(5, self.d._amount_to_contracts("ETH-USDT", Decimal("5")))

    def test_contracts_to_amount_basic(self):
        """1000 contracts × 0.001 = 1.0 BTC."""
        self.d._contract_sizes[_TRADING_PAIR] = Decimal("0.001")
        self.assertEqual(Decimal("1.000"), self.d._contracts_to_amount(_TRADING_PAIR, 1000))

    def test_contracts_to_amount_missing_key_defaults_to_1(self):
        """Missing contract size defaults to 1."""
        self.assertEqual(Decimal("7"), self.d._contracts_to_amount("ETH-USDT", 7))

    def test_roundtrip_amount_contracts(self):
        """Converting amount→contracts→amount is lossless for exact multiples."""
        self.d._contract_sizes[_TRADING_PAIR] = Decimal("0.01")
        contracts = self.d._amount_to_contracts(_TRADING_PAIR, Decimal("5.0"))
        back = self.d._contracts_to_amount(_TRADING_PAIR, contracts)
        self.assertEqual(Decimal("5.0"), back)


# ---------------------------------------------------------------------------
# 6. Position processing
# ---------------------------------------------------------------------------

class TestLmexPerpetualPositionProcessing(unittest.TestCase):

    def setUp(self):
        self.d = _make_derivative()
        self.d._contract_sizes[_TRADING_PAIR] = Decimal("0.001")

    def test_long_position_set(self):
        """A BUY-side position with total > 0 calls set_position with LONG side."""
        _run(self.d._process_position_data({
            "symbol": _EX_SYMBOL,
            "side": "BUY",
            "total": 100,
            "entryPrice": "50000",
            "unrealizedPnl": "10",
            "currentLeverage": "10",
        }))
        self.d._perpetual_trading.set_position.assert_called_once()
        pos = self.d._perpetual_trading.set_position.call_args[0][1]
        self.assertEqual(PositionSide.LONG, pos.position_side)

    def test_short_position_set(self):
        """A SELL-side position with total > 0 calls set_position with SHORT side."""
        _run(self.d._process_position_data({
            "symbol": _EX_SYMBOL,
            "side": "SELL",
            "total": 50,
            "entryPrice": "50000",
            "unrealizedPnl": "-5",
            "currentLeverage": "5",
        }))
        pos = self.d._perpetual_trading.set_position.call_args[0][1]
        self.assertEqual(PositionSide.SHORT, pos.position_side)

    def test_zero_total_removes_position(self):
        """A position with total=0 calls remove_position instead of set."""
        _run(self.d._process_position_data({
            "symbol": _EX_SYMBOL,
            "side": "BUY",
            "total": 0,
        }))
        self.d._perpetual_trading.remove_position.assert_called_once()
        self.d._perpetual_trading.set_position.assert_not_called()

    def test_missing_symbol_returns_without_error(self):
        """Position data without a symbol key is silently ignored."""
        _run(self.d._process_position_data({"side": "BUY", "total": 10}))
        self.d._perpetual_trading.set_position.assert_not_called()
        self.d._perpetual_trading.remove_position.assert_not_called()

    def test_unknown_symbol_skips_gracefully(self):
        """If trading_pair lookup raises, position processing is skipped."""
        self.d.trading_pair_associated_to_exchange_symbol = AsyncMock(side_effect=KeyError("unknown"))
        _run(self.d._process_position_data({"symbol": "XXX-PERP", "side": "BUY", "total": 10}))
        self.d._perpetual_trading.set_position.assert_not_called()

    def test_position_amount_calculated_from_contracts(self):
        """Position amount is contractSize × total_contracts."""
        _run(self.d._process_position_data({
            "symbol": _EX_SYMBOL,
            "side": "BUY",
            "total": 500,
            "entryPrice": "50000",
            "unrealizedPnl": "0",
            "currentLeverage": "1",
        }))
        pos = self.d._perpetual_trading.set_position.call_args[0][1]
        self.assertEqual(Decimal("0.5"), pos.amount)  # 500 × 0.001

    def test_leverage_set_on_position(self):
        """The leverage value from API is stored on the position."""
        _run(self.d._process_position_data({
            "symbol": _EX_SYMBOL,
            "side": "BUY",
            "total": 100,
            "entryPrice": "50000",
            "unrealizedPnl": "0",
            "currentLeverage": "20",
        }))
        pos = self.d._perpetual_trading.set_position.call_args[0][1]
        self.assertEqual(Decimal("20"), pos.leverage)


# ---------------------------------------------------------------------------
# 7. Trade update from fill
# ---------------------------------------------------------------------------

class TestLmexPerpetualTradeUpdate(unittest.TestCase):

    def setUp(self):
        self.d = _make_derivative()
        self.d._contract_sizes[_TRADING_PAIR] = Decimal("0.001")

    def _fill(self, **kwargs):
        base = {
            "size": 100,
            "price": "50000",
            "feeAmount": "2.5",
            "timestamp": _TS_MS,
            "tradeId": "TRADE-001",
            "orderID": "EX-UUID-1234",
            "orderAction": "OPEN",
        }
        base.update(kwargs)
        return base

    def test_fill_amount_from_contracts(self):
        """Fill amount = contractSize × fill_size."""
        tu = self.d._create_trade_update_from_fill(self._fill(size=100), _make_in_flight_order())
        self.assertEqual(Decimal("0.1"), tu.fill_base_amount)

    def test_fill_price_set(self):
        """fill_price is taken from the fill record."""
        tu = self.d._create_trade_update_from_fill(self._fill(price="49999"), _make_in_flight_order())
        self.assertEqual(Decimal("49999"), tu.fill_price)

    def test_trade_id_from_trade_id_key(self):
        """tradeId field is used as trade_id when present."""
        tu = self.d._create_trade_update_from_fill(self._fill(tradeId="T-XYZ"), _make_in_flight_order())
        self.assertEqual("T-XYZ", tu.trade_id)

    def test_trade_id_falls_back_to_serial_id(self):
        """serialId is used as trade_id when tradeId is absent."""
        fill = self._fill()
        del fill["tradeId"]
        fill["serialId"] = "SER-999"
        tu = self.d._create_trade_update_from_fill(fill, _make_in_flight_order())
        self.assertEqual("SER-999", tu.trade_id)

    def test_fill_timestamp_in_seconds(self):
        """Millisecond timestamp is divided by 1000."""
        tu = self.d._create_trade_update_from_fill(self._fill(timestamp=_TS_MS), _make_in_flight_order())
        self.assertAlmostEqual(_TS_S, tu.fill_timestamp, places=0)

    def test_fill_quote_amount_is_amount_times_price(self):
        """fill_quote_amount = fill_base_amount × fill_price."""
        tu = self.d._create_trade_update_from_fill(self._fill(size=100, price="50000"), _make_in_flight_order())
        expected = Decimal("0.1") * Decimal("50000")
        self.assertAlmostEqual(float(expected), float(tu.fill_quote_amount), places=4)


# ---------------------------------------------------------------------------
# 8. Leverage
# ---------------------------------------------------------------------------

class TestLmexPerpetualLeverage(unittest.TestCase):

    def setUp(self):
        self.d = _make_derivative()

    def _mock_api_post(self, response):
        self.d._api_post = AsyncMock(return_value=response)

    def test_leverage_set_returns_true(self):
        """Correct leverage response returns (True, '')."""
        self._mock_api_post([{"leverage": 10}])
        ok, msg = _run(self.d._set_trading_pair_leverage(_TRADING_PAIR, 10))
        self.assertTrue(ok)
        self.assertEqual("", msg)

    def test_leverage_mismatch_returns_false(self):
        """Mismatched leverage in response returns (False, message)."""
        self._mock_api_post([{"leverage": 5}])
        ok, msg = _run(self.d._set_trading_pair_leverage(_TRADING_PAIR, 10))
        self.assertFalse(ok)
        self.assertIn("5", msg)

    def test_api_exception_returns_false(self):
        """An API exception returns (False, error_string)."""
        self.d._api_post = AsyncMock(side_effect=Exception("connection error"))
        ok, msg = _run(self.d._set_trading_pair_leverage(_TRADING_PAIR, 10))
        self.assertFalse(ok)
        self.assertIn("connection error", msg)

    def test_leverage_dict_response_accepted(self):
        """A dict (not list) response is also handled correctly."""
        self._mock_api_post({"leverage": 20})
        ok, msg = _run(self.d._set_trading_pair_leverage(_TRADING_PAIR, 20))
        self.assertTrue(ok)


# ---------------------------------------------------------------------------
# 9. Position mode
# ---------------------------------------------------------------------------

class TestLmexPerpetualPositionMode(unittest.TestCase):

    def setUp(self):
        self.d = _make_derivative()

    def test_get_position_mode_returns_oneway(self):
        """_get_position_mode always returns ONEWAY."""
        result = _run(self.d._get_position_mode())
        self.assertEqual(PositionMode.ONEWAY, result)

    def test_oneway_mode_accepted(self):
        """Setting ONEWAY mode returns (True, pairs, '')."""
        ok, pairs, msg = _run(
            self.d._execute_set_position_mode_for_pairs(PositionMode.ONEWAY, [_TRADING_PAIR])
        )
        self.assertTrue(ok)
        self.assertEqual([_TRADING_PAIR], pairs)
        self.assertEqual("", msg)

    def test_hedge_mode_rejected(self):
        """Setting HEDGE mode returns (False, [], error message)."""
        ok, pairs, msg = _run(
            self.d._execute_set_position_mode_for_pairs(PositionMode.HEDGE, [_TRADING_PAIR])
        )
        self.assertFalse(ok)
        self.assertEqual([], pairs)
        self.assertIn("ONEWAY", msg)

    def test_supported_position_modes(self):
        """supported_position_modes() returns only [ONEWAY]."""
        modes = self.d.supported_position_modes()
        self.assertEqual([PositionMode.ONEWAY], modes)


# ---------------------------------------------------------------------------
# 10. Order message processing
# ---------------------------------------------------------------------------

class TestLmexPerpetualOrderMessageProcessing(unittest.TestCase):

    def setUp(self):
        self.d = _make_derivative()

    def _tracked_order(self, cl_id):
        o = _make_in_flight_order(client_order_id=cl_id)
        return o

    def test_clOrderId_key_routes_correctly(self):
        """clOrderId (lower-case d) is the primary key for tracked orders."""
        order = self._tracked_order("HBOT-ABC")
        self.d._order_tracker.all_updatable_orders = {"HBOT-ABC": order}
        self.d._process_order_message({
            "clOrderId": "HBOT-ABC",
            "status": 4,
            "orderID": "EX-1",
            "timestamp": _TS_MS,
        })
        self.d._order_tracker.process_order_update.assert_called_once()

    def test_clOrderID_uppercase_fallback(self):
        """clOrderID (upper-case D) is used if clOrderId is absent."""
        order = self._tracked_order("HBOT-DEF")
        self.d._order_tracker.all_updatable_orders = {"HBOT-DEF": order}
        self.d._process_order_message({
            "clOrderID": "HBOT-DEF",
            "status": 2,
            "orderID": "EX-2",
            "timestamp": _TS_MS,
        })
        self.d._order_tracker.process_order_update.assert_called_once()

    def test_unknown_client_id_skipped(self):
        """Messages for unknown client order IDs are silently ignored."""
        self.d._order_tracker.all_updatable_orders = {}
        self.d._process_order_message({"clOrderId": "UNKNOWN", "status": 4, "orderID": "EX"})
        self.d._order_tracker.process_order_update.assert_not_called()


# ---------------------------------------------------------------------------
# 11. Trade message processing
# ---------------------------------------------------------------------------

class TestLmexPerpetualTradeMessageProcessing(unittest.TestCase):

    def setUp(self):
        self.d = _make_derivative()

    def test_known_order_routes_to_trade_update(self):
        """A fill for a tracked order is forwarded to process_trade_update."""
        order = _make_in_flight_order(client_order_id="HBOT-XYZ")
        self.d._order_tracker.all_fillable_orders = {"HBOT-XYZ": order}
        self.d._contract_sizes[_TRADING_PAIR] = Decimal("0.001")
        self.d._process_trade_message({
            "clOrderId": "HBOT-XYZ",
            "size": 10,
            "price": "50000",
            "feeAmount": "1",
            "timestamp": _TS_MS,
            "tradeId": "T-1",
            "orderID": "EX-1",
            "orderAction": "OPEN",
        })
        self.d._order_tracker.process_trade_update.assert_called_once()

    def test_unknown_order_skipped(self):
        """A fill for an unknown client order ID is silently ignored."""
        self.d._order_tracker.all_fillable_orders = {}
        self.d._process_trade_message({"clOrderId": "UNKNOWN", "size": 1})
        self.d._order_tracker.process_trade_update.assert_not_called()


# ---------------------------------------------------------------------------
# 12. Properties and error classifiers
# ---------------------------------------------------------------------------

class TestLmexPerpetualProperties(unittest.TestCase):

    def setUp(self):
        self.d = _make_derivative()

    def test_name_is_lmex_perpetual(self):
        """name property returns 'lmex_perpetual'."""
        self.assertEqual("lmex_perpetual", self.d.name)

    def test_client_order_id_prefix(self):
        """client_order_id_prefix is 'x-HBOT'."""
        self.assertEqual("x-HBOT", self.d.client_order_id_prefix)

    def test_client_order_id_max_length(self):
        """client_order_id_max_length is 32."""
        self.assertEqual(32, self.d.client_order_id_max_length)

    def test_supported_order_types(self):
        """supported_order_types includes LIMIT, MARKET, LIMIT_MAKER."""
        types = self.d.supported_order_types()
        self.assertIn(OrderType.LIMIT, types)
        self.assertIn(OrderType.MARKET, types)
        self.assertIn(OrderType.LIMIT_MAKER, types)

    def test_buy_collateral_token_is_usdt(self):
        """get_buy_collateral_token returns 'USDT' for any pair."""
        self.assertEqual("USDT", self.d.get_buy_collateral_token(_TRADING_PAIR))

    def test_sell_collateral_token_is_usdt(self):
        """get_sell_collateral_token returns 'USDT' for any pair."""
        self.assertEqual("USDT", self.d.get_sell_collateral_token(_TRADING_PAIR))

    def test_funding_fee_poll_interval(self):
        """funding_fee_poll_interval is 3600 seconds."""
        self.assertEqual(3600, self.d.funding_fee_poll_interval)

    def test_is_cancel_request_synchronous(self):
        """is_cancel_request_in_exchange_synchronous is True."""
        self.assertTrue(self.d.is_cancel_request_in_exchange_synchronous)

    def test_time_synchronizer_error_always_false(self):
        """_is_request_exception_related_to_time_synchronizer always returns False."""
        self.assertFalse(
            self.d._is_request_exception_related_to_time_synchronizer(Exception("any"))
        )

    def test_order_not_found_status_update_always_false(self):
        """_is_order_not_found_during_status_update_error always returns False."""
        self.assertFalse(
            self.d._is_order_not_found_during_status_update_error(Exception("16"))
        )

    def test_order_not_found_cancel_always_false(self):
        """_is_order_not_found_during_cancelation_error always returns False."""
        self.assertFalse(
            self.d._is_order_not_found_during_cancelation_error(Exception("16"))
        )


if __name__ == "__main__":
    unittest.main()
