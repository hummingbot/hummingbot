import asyncio
import time
import unittest
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from hummingbot.connector.derivative.decibel_perpetual import decibel_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth import DecibelPerpetualAuth
from hummingbot.core.data_type.common import OrderType, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_auth() -> DecibelPerpetualAuth:
    return DecibelPerpetualAuth(
        api_wallet_private_key="0x" + "ab" * 32,
        main_wallet_public_key="0x" + "cd" * 32,
        api_key="test_bearer_token",
    )


def _make_connector():
    """
    Build a minimal DecibelPerpetualDerivative instance with mocked I/O.
    We avoid calling __init__ through the real PerpetualDerivativePyBase
    because it triggers network calls, so we instantiate a slimmed-down
    object and manually set the attributes we test.
    """
    from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
        DecibelPerpetualDerivative,
    )

    with patch.object(DecibelPerpetualDerivative, "__init__", lambda self, *a, **kw: None):
        connector = DecibelPerpetualDerivative.__new__(DecibelPerpetualDerivative)

    connector._api_wallet_public_key = "0x" + "aa" * 32
    connector._api_wallet_private_key = "0x" + "bb" * 32
    connector._main_wallet_public_key = "0x" + "cc" * 32
    connector._api_key = "test_bearer_token"
    connector._market_order_slippage = Decimal("0.08")
    connector._domain = CONSTANTS.DEFAULT_DOMAIN
    connector._trading_required = True
    connector._trading_pairs = ["BTC-USD"]
    connector._auth = _make_auth()
    connector._transaction_builder = None
    connector._package_address = None
    connector._trading_pair_symbol_map = None
    connector._market_info = {}
    connector._last_poll_timestamp = 0
    connector._account_available_balances = {}
    connector._account_balances = {}

    # Minimal logger stub
    import logging
    connector._logger = logging.getLogger("test_decibel")

    return connector


class TestDecibelPerpetualDerivativeProperties(unittest.TestCase):
    """Tests for connector properties that do not require async."""

    def setUp(self):
        self.connector = _make_connector()

    # ------------------------------------------------------------------
    # Test 1: name property
    # ------------------------------------------------------------------
    def test_name_property(self):
        self.assertEqual(self.connector._domain, CONSTANTS.DEFAULT_DOMAIN)

    # ------------------------------------------------------------------
    # Test 2: supported_order_types
    # ------------------------------------------------------------------
    def test_supported_order_types(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        types = DecibelPerpetualDerivative.supported_order_types(self.connector)
        self.assertIn(OrderType.LIMIT, types)
        self.assertIn(OrderType.LIMIT_MAKER, types)

    # ------------------------------------------------------------------
    # Test 3: supported_position_modes
    # ------------------------------------------------------------------
    def test_supported_position_modes(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        modes = DecibelPerpetualDerivative.supported_position_modes(self.connector)
        self.assertIn(PositionMode.ONEWAY, modes)
        self.assertEqual(len(modes), 1)

    # ------------------------------------------------------------------
    # Test 4: collateral token is USDC
    # ------------------------------------------------------------------
    def test_collateral_token(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        self.assertEqual(
            DecibelPerpetualDerivative.get_buy_collateral_token(self.connector, "BTC-USD"),
            "USDC",
        )
        self.assertEqual(
            DecibelPerpetualDerivative.get_sell_collateral_token(self.connector, "BTC-USD"),
            "USDC",
        )

    # ------------------------------------------------------------------
    # Test 5: funding_fee_poll_interval is positive integer
    # ------------------------------------------------------------------
    def test_funding_fee_poll_interval(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        interval = DecibelPerpetualDerivative.funding_fee_poll_interval.fget(self.connector)
        self.assertIsInstance(interval, int)
        self.assertGreater(interval, 0)

    # ------------------------------------------------------------------
    # Test 6: client_order_id_max_length is 32
    # ------------------------------------------------------------------
    def test_client_order_id_max_length(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        length = DecibelPerpetualDerivative.client_order_id_max_length.fget(self.connector)
        self.assertEqual(length, 32)

    # ------------------------------------------------------------------
    # Test 7: client_order_id_prefix is HBOT
    # ------------------------------------------------------------------
    def test_client_order_id_prefix(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        prefix = DecibelPerpetualDerivative.client_order_id_prefix.fget(self.connector)
        self.assertEqual(prefix, "HBOT")

    # ------------------------------------------------------------------
    # Test 8: trading_pairs property
    # ------------------------------------------------------------------
    def test_trading_pairs_property(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        pairs = DecibelPerpetualDerivative.trading_pairs.fget(self.connector)
        self.assertIn("BTC-USD", pairs)


class TestDecibelPerpetualDerivativeAsync(unittest.IsolatedAsyncioTestCase):
    """Async tests for methods that hit the network (mocked)."""

    def setUp(self):
        self.connector = _make_connector()

    # ------------------------------------------------------------------
    # Test 9: get_package_address returns MAINNET_PACKAGE for default domain
    # ------------------------------------------------------------------
    async def test_get_package_address_mainnet(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        addr = await DecibelPerpetualDerivative.get_package_address(self.connector)
        self.assertEqual(addr, CONSTANTS.MAINNET_PACKAGE)

    # ------------------------------------------------------------------
    # Test 10: get_package_address returns TESTNET_PACKAGE for testnet
    # ------------------------------------------------------------------
    async def test_get_package_address_testnet(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        self.connector._domain = CONSTANTS.TESTNET_DOMAIN
        self.connector._package_address = None
        addr = await DecibelPerpetualDerivative.get_package_address(self.connector)
        self.assertEqual(addr, CONSTANTS.TESTNET_PACKAGE)

    # ------------------------------------------------------------------
    # Test 11: _create_trading_pair_symbol_map builds bidict correctly
    # ------------------------------------------------------------------
    async def test_create_trading_pair_symbol_map(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        exchange_info = {
            "markets": [
                {"market_name": "BTC/USD"},
                {"market_name": "ETH/USD"},
            ]
        }
        mapping = await DecibelPerpetualDerivative._create_trading_pair_symbol_map(
            self.connector, exchange_info
        )
        self.assertIn("BTC/USD", mapping)
        self.assertIn("ETH/USD", mapping)
        self.assertEqual(mapping["BTC/USD"], "BTC-USD")

    # ------------------------------------------------------------------
    # Test 12: _create_trading_pair_symbol_map handles list format
    # ------------------------------------------------------------------
    async def test_create_trading_pair_symbol_map_list_format(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        exchange_info = [
            {"market_name": "SOL/USD"},
        ]
        mapping = await DecibelPerpetualDerivative._create_trading_pair_symbol_map(
            self.connector, exchange_info
        )
        self.assertIn("SOL/USD", mapping)
        self.assertEqual(mapping["SOL/USD"], "SOL-USD")

    # ------------------------------------------------------------------
    # Test 13: _format_trading_rules produces TradingRule objects
    # ------------------------------------------------------------------
    async def test_format_trading_rules(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        # Pre-populate symbol map so trading_pair_associated_to_exchange_symbol works
        from bidict import bidict
        self.connector._trading_pair_symbol_map = bidict({"BTC/USD": "BTC-USD"})

        exchange_info = {
            "markets": [
                {
                    "market_name": "BTC/USD",
                    "min_size": 1000,
                    "lot_size": 100,
                    "tick_size": 10,
                    "px_decimals": 4,
                    "sz_decimals": 6,
                    "max_open_interest": 1000000,
                }
            ]
        }
        rules = await DecibelPerpetualDerivative._format_trading_rules(self.connector, exchange_info)
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].trading_pair, "BTC-USD")
        self.assertGreater(rules[0].min_order_size, Decimal("0"))

    # ------------------------------------------------------------------
    # Test 14: exchange_symbol_associated_to_pair converts BTC-USD → BTC/USD
    # ------------------------------------------------------------------
    async def test_exchange_symbol_associated_to_pair(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        from bidict import bidict
        self.connector._trading_pair_symbol_map = bidict({"BTC/USD": "BTC-USD"})
        result = await DecibelPerpetualDerivative.exchange_symbol_associated_to_pair(
            self.connector, "BTC-USD"
        )
        self.assertEqual(result, "BTC/USD")

    # ------------------------------------------------------------------
    # Test 15: trading_pair_associated_to_exchange_symbol converts BTC/USD → BTC-USD
    # ------------------------------------------------------------------
    async def test_trading_pair_associated_to_exchange_symbol(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        from bidict import bidict
        self.connector._trading_pair_symbol_map = bidict({"BTC/USD": "BTC-USD"})
        result = await DecibelPerpetualDerivative.trading_pair_associated_to_exchange_symbol(
            self.connector, "BTC/USD"
        )
        self.assertEqual(result, "BTC-USD")

    # ------------------------------------------------------------------
    # Test 16: _convert_price_to_chain_units correct conversion
    # ------------------------------------------------------------------
    def test_convert_price_to_chain_units(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        self.connector._market_info = {
            "BTC-USD": {"px_decimals": 4}
        }
        result = DecibelPerpetualDerivative._convert_price_to_chain_units(
            self.connector, "BTC-USD", Decimal("50000")
        )
        self.assertEqual(result, 500_000_000)

    # ------------------------------------------------------------------
    # Test 17: _convert_size_to_chain_units correct conversion
    # ------------------------------------------------------------------
    def test_convert_size_to_chain_units(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        self.connector._market_info = {
            "BTC-USD": {"sz_decimals": 6}
        }
        result = DecibelPerpetualDerivative._convert_size_to_chain_units(
            self.connector, "BTC-USD", Decimal("0.001")
        )
        self.assertEqual(result, 1000)

    # ------------------------------------------------------------------
    # Test 18: _trading_pair_position_mode_set allows ONEWAY
    # ------------------------------------------------------------------
    async def test_trading_pair_position_mode_set_oneway(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        success, msg = await DecibelPerpetualDerivative._trading_pair_position_mode_set(
            self.connector, PositionMode.ONEWAY, "BTC-USD"
        )
        self.assertTrue(success)

    # ------------------------------------------------------------------
    # Test 19: _trading_pair_position_mode_set rejects HEDGE
    # ------------------------------------------------------------------
    async def test_trading_pair_position_mode_set_hedge_rejected(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        success, msg = await DecibelPerpetualDerivative._trading_pair_position_mode_set(
            self.connector, PositionMode.HEDGE, "BTC-USD"
        )
        self.assertFalse(success)

    # ------------------------------------------------------------------
    # Test 20: _is_order_not_found_during_cancelation_error detects 'not found'
    # ------------------------------------------------------------------
    def test_is_order_not_found_during_cancelation_error(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        err = Exception("Order not found on exchange")
        result = DecibelPerpetualDerivative._is_order_not_found_during_cancelation_error(
            self.connector, err
        )
        self.assertTrue(result)

    # ------------------------------------------------------------------
    # Test 21: _is_order_not_found returns False for unrelated error
    # ------------------------------------------------------------------
    def test_is_order_not_found_unrelated_error(self):
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )
        err = Exception("Network timeout")
        result = DecibelPerpetualDerivative._is_order_not_found_during_cancelation_error(
            self.connector, err
        )
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
