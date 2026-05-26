"""
Unit tests for LmexExchange — focused on the pure-Python logic that does NOT
require a running event loop, network, or the full Hummingbot runtime.

Covered:
  - _LMEX_STATUS_TO_ORDER_STATE mapping completeness and correctness
  - _process_balance_message: sets total/available, removes stale assets
  - _create_order_update_from_order_data: status mapping, timestamp normalisation,
    clOrderID fallback, millisecond→second conversion
  - _is_request_exception_related_to_time_synchronizer always returns False
  - _is_order_not_found_during_status_update_error / cancelation detection
  - supported_order_types returns LIMIT, MARKET, LIMIT_MAKER
  - name property returns "lmex"
"""
import asyncio
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch, AsyncMock

from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import OrderState


# ---------------------------------------------------------------------------
# Helpers: build a minimal LmexExchange without triggering super().__init__
# ---------------------------------------------------------------------------

def _make_exchange():
    """
    Construct a LmexExchange with super().__init__ patched out so we don't need
    all of Hummingbot's async infrastructure (throttlers, web assistants, etc.).
    """
    from hummingbot.connector.exchange.lmex.lmex_exchange import LmexExchange

    with patch.object(LmexExchange.__bases__[0], "__init__", return_value=None):
        exc = LmexExchange.__new__(LmexExchange)
        exc._lmex_api_key = "api_key_test"
        exc._lmex_secret_key = "secret_key_test"
        exc._domain = ""
        exc._trading_pairs = ["BTC-USD"]
        exc._trading_required = True
        exc._account_balances = {}
        exc._account_available_balances = {}
        exc.current_timestamp = 1677663813.822
        return exc


def _make_in_flight_order(client_order_id="HBOT-001", exchange_order_id="EX-12345",
                           trading_pair="BTC-USD", current_state=OrderState.OPEN):
    order = MagicMock()
    order.client_order_id = client_order_id
    order.exchange_order_id = exchange_order_id
    order.trading_pair = trading_pair
    order.current_state = current_state
    return order


# ---------------------------------------------------------------------------
# Status mapping
# ---------------------------------------------------------------------------
class TestLmexStatusMapping(unittest.TestCase):

    def _get_mapping(self):
        from hummingbot.connector.exchange.lmex.lmex_exchange import _LMEX_STATUS_TO_ORDER_STATE
        return _LMEX_STATUS_TO_ORDER_STATE

    def test_open_statuses(self):
        m = self._get_mapping()
        open_codes = [2, 5, 9, 10, 65, 85, 88]
        for code in open_codes:
            with self.subTest(code=code):
                self.assertIn(code, m, f"Status code {code} missing from mapping")
                self.assertIn(
                    m[code], (OrderState.OPEN, OrderState.PARTIALLY_FILLED),
                    f"Status {code} should map to OPEN or PARTIALLY_FILLED"
                )

    def test_filled_status(self):
        m = self._get_mapping()
        self.assertEqual(OrderState.FILLED, m[4])

    def test_cancelled_statuses(self):
        m = self._get_mapping()
        for code in [6, 7]:
            with self.subTest(code=code):
                self.assertEqual(OrderState.CANCELED, m[code])

    def test_failed_statuses(self):
        m = self._get_mapping()
        for code in [8, 15, 16, 17]:
            with self.subTest(code=code):
                self.assertEqual(OrderState.FAILED, m[code])

    def test_no_duplicate_terminal_states(self):
        """Status code 4 (FILLED) must not also appear in OPEN set."""
        m = self._get_mapping()
        self.assertNotEqual(OrderState.OPEN, m[4])
        self.assertNotEqual(OrderState.CANCELED, m[4])


# ---------------------------------------------------------------------------
# Balance processing
# ---------------------------------------------------------------------------
class TestLmexProcessBalanceMessage(unittest.TestCase):

    def setUp(self):
        self.exc = _make_exchange()

    def test_sets_total_balance(self):
        wallet = [{"currency": "BTC", "total": "1.5", "available": "1.0"}]
        self.exc._process_balance_message(wallet)
        self.assertEqual(Decimal("1.5"), self.exc._account_balances["BTC"])

    def test_sets_available_balance(self):
        wallet = [{"currency": "BTC", "total": "1.5", "available": "1.0"}]
        self.exc._process_balance_message(wallet)
        self.assertEqual(Decimal("1.0"), self.exc._account_available_balances["BTC"])

    def test_multiple_currencies(self):
        wallet = [
            {"currency": "BTC", "total": "0.5", "available": "0.5"},
            {"currency": "USD", "total": "10000", "available": "9000"},
        ]
        self.exc._process_balance_message(wallet)
        self.assertIn("BTC", self.exc._account_balances)
        self.assertIn("USD", self.exc._account_balances)
        self.assertEqual(Decimal("9000"), self.exc._account_available_balances["USD"])

    def test_stale_asset_removed(self):
        """An asset that disappears from the wallet response must be removed from local state."""
        self.exc._account_balances["ETH"] = Decimal("5")
        self.exc._account_available_balances["ETH"] = Decimal("5")
        wallet = [{"currency": "BTC", "total": "1", "available": "1"}]
        self.exc._process_balance_message(wallet)
        self.assertNotIn("ETH", self.exc._account_balances)
        self.assertNotIn("ETH", self.exc._account_available_balances)

    def test_empty_wallet_clears_balances(self):
        self.exc._account_balances["BTC"] = Decimal("1")
        self.exc._account_available_balances["BTC"] = Decimal("1")
        self.exc._process_balance_message([])
        self.assertEqual({}, self.exc._account_balances)


# ---------------------------------------------------------------------------
# Order update from order data
# ---------------------------------------------------------------------------
class TestLmexCreateOrderUpdate(unittest.TestCase):

    def setUp(self):
        self.exc = _make_exchange()

    def _run_update(self, order_data, order=None):
        if order is None:
            order = _make_in_flight_order()
        return self.exc._create_order_update_from_order_data(order_data, order)

    def test_filled_status(self):
        update = self._run_update({"status": 4, "orderID": "EX-1", "clOrderID": "HBOT-001",
                                   "timestamp": 1677663813822})
        self.assertEqual(OrderState.FILLED, update.new_state)

    def test_cancelled_status(self):
        update = self._run_update({"status": 6, "orderID": "EX-1", "clOrderID": "HBOT-001",
                                   "timestamp": 1677663813822})
        self.assertEqual(OrderState.CANCELED, update.new_state)

    def test_failed_status(self):
        update = self._run_update({"status": 15, "orderID": "EX-1", "clOrderID": "HBOT-001",
                                   "timestamp": 1677663813822})
        self.assertEqual(OrderState.FAILED, update.new_state)

    def test_unknown_status_falls_back_to_current_state(self):
        order = _make_in_flight_order(current_state=OrderState.OPEN)
        update = self._run_update({"status": 999, "orderID": "EX-1", "clOrderID": "HBOT-001",
                                   "timestamp": 1677663813822}, order=order)
        self.assertEqual(OrderState.OPEN, update.new_state)

    def test_millisecond_timestamp_converted_to_seconds(self):
        ts_ms = 1677663813822
        update = self._run_update({"status": 4, "orderID": "EX-1",
                                   "clOrderID": "HBOT-001", "timestamp": ts_ms})
        self.assertAlmostEqual(ts_ms / 1e3, update.update_timestamp, places=0)

    def test_second_timestamp_not_double_divided(self):
        """A timestamp ≤ 1e10 (already in seconds) must not be divided again."""
        ts_s = 1677663813.0
        update = self._run_update({"status": 4, "orderID": "EX-1",
                                   "clOrderID": "HBOT-001", "timestamp": ts_s})
        self.assertAlmostEqual(ts_s, update.update_timestamp, places=0)

    def test_cl_order_id_echoed(self):
        update = self._run_update({"status": 2, "orderID": "EX-99",
                                   "clOrderID": "HBOT-999", "timestamp": 0})
        self.assertEqual("HBOT-999", update.client_order_id)

    def test_exchange_order_id_set(self):
        update = self._run_update({"status": 2, "orderID": "EX-42",
                                   "clOrderID": "HBOT-001", "timestamp": 0})
        self.assertEqual("EX-42", update.exchange_order_id)

    def test_missing_timestamp_uses_current(self):
        """When 'timestamp' is absent the update_timestamp must be connector's current_timestamp."""
        update = self._run_update({"status": 4, "orderID": "EX-1", "clOrderID": "HBOT-001"})
        self.assertEqual(self.exc.current_timestamp, update.update_timestamp)


# ---------------------------------------------------------------------------
# Exception classification
# ---------------------------------------------------------------------------
class TestLmexExceptionClassification(unittest.TestCase):

    def setUp(self):
        self.exc = _make_exchange()

    def test_time_synchronizer_error_always_false(self):
        """LMEX uses nonce, so no time-sync errors should be classified."""
        self.assertFalse(
            self.exc._is_request_exception_related_to_time_synchronizer(
                Exception("any error")
            )
        )

    def test_order_not_found_status_update(self):
        """Error message containing ORDER_STATUS_NOT_FOUND (16) must be recognised."""
        err = Exception(f"Order status 16 not found")
        self.assertTrue(self.exc._is_order_not_found_during_status_update_error(err))

    def test_order_not_found_false_for_other_errors(self):
        err = Exception("Insufficient balance")
        self.assertFalse(self.exc._is_order_not_found_during_status_update_error(err))

    def test_order_not_found_cancelation(self):
        err = Exception("cancel failed: code 16")
        self.assertTrue(self.exc._is_order_not_found_during_cancelation_error(err))


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------
class TestLmexExchangeProperties(unittest.TestCase):

    def setUp(self):
        self.exc = _make_exchange()

    def test_name_is_lmex(self):
        self.assertEqual("lmex", self.exc.name)

    def test_supported_order_types(self):
        types = self.exc.supported_order_types()
        self.assertIn(OrderType.LIMIT, types)
        self.assertIn(OrderType.MARKET, types)
        self.assertIn(OrderType.LIMIT_MAKER, types)

    def test_client_order_id_prefix(self):
        self.assertEqual("HBOT-", self.exc.client_order_id_prefix)

    def test_client_order_id_max_length(self):
        self.assertEqual(36, self.exc.client_order_id_max_length)

    def test_is_cancel_request_synchronous(self):
        self.assertTrue(self.exc.is_cancel_request_in_exchange_synchronous)


if __name__ == "__main__":
    unittest.main()
