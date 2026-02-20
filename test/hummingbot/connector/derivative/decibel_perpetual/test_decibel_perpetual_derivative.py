import asyncio
import time
import unittest
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from hummingbot.connector.derivative.decibel_perpetual import decibel_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
    DecibelPerpetualDerivative,
)
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_web_utils import (
    int_to_price,
    int_to_size,
    price_to_int,
    size_to_int,
)
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState


class TestDecibelPerpetualDerivative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.get_event_loop()

    def setUp(self):
        self.connector = DecibelPerpetualDerivative(
            decibel_perpetual_api_key="test_api_key",
            decibel_perpetual_account_address="0xtest_account_address",
            decibel_perpetual_subaccount_address="0xtest_subaccount_address",
            decibel_perpetual_private_key="0xtest_private_key",
            trading_pairs=["BTC-USD"],
            trading_required=False,
            domain=CONSTANTS.DOMAIN,
        )

    # ===== Price/Size Conversion Tests =====

    def test_price_to_int(self):
        """Test price conversion to 9-decimal integer format."""
        self.assertEqual(price_to_int(97250.0), 97250_000_000_000)
        self.assertEqual(price_to_int(1.0), 1_000_000_000)
        self.assertEqual(price_to_int(0.5), 500_000_000)

    def test_size_to_int(self):
        """Test size conversion to 9-decimal integer format."""
        self.assertEqual(size_to_int(1.5), 1_500_000_000)
        self.assertEqual(size_to_int(0.001), 1_000_000)

    def test_int_to_price(self):
        """Test integer to price conversion."""
        self.assertAlmostEqual(int_to_price(97250_000_000_000), 97250.0)
        self.assertAlmostEqual(int_to_price(1_000_000_000), 1.0)

    def test_int_to_size(self):
        """Test integer to size conversion."""
        self.assertAlmostEqual(int_to_size(1_500_000_000), 1.5)

    # ===== Properties Tests =====

    def test_name(self):
        self.assertEqual(self.connector.name, CONSTANTS.DOMAIN)

    def test_supported_order_types(self):
        order_types = self.connector.supported_order_types()
        self.assertIn(OrderType.LIMIT, order_types)
        self.assertIn(OrderType.LIMIT_MAKER, order_types)
        self.assertIn(OrderType.MARKET, order_types)

    def test_supported_position_modes(self):
        modes = self.connector.supported_position_modes()
        self.assertEqual(modes, [PositionMode.ONEWAY])

    def test_is_cancel_request_in_exchange_synchronous(self):
        self.assertTrue(self.connector.is_cancel_request_in_exchange_synchronous)

    def test_funding_fee_poll_interval(self):
        self.assertEqual(self.connector.funding_fee_poll_interval, 120)

    # ===== Trading Rules Tests =====

    def test_format_trading_rules(self):
        mock_markets = [
            {
                "symbol": "BTC-PERP",
                "market_address": "0xmarket_btc",
                "base_currency": "BTC",
                "quote_currency": "USD",
                "tick_size": "0.1",
                "step_size": "0.001",
                "min_order_size": "0.001",
            },
            {
                "symbol": "ETH-PERP",
                "market_address": "0xmarket_eth",
                "base_currency": "ETH",
                "quote_currency": "USD",
                "tick_size": "0.01",
                "step_size": "0.01",
                "min_order_size": "0.01",
            },
        ]
        # Need symbol map for trading_pair_associated_to_exchange_symbol
        self.connector._initialize_trading_pair_symbols_from_exchange_info(mock_markets)
        rules = self.ev_loop.run_until_complete(
            self.connector._format_trading_rules(mock_markets)
        )
        self.assertEqual(len(rules), 2)
        self.assertIsInstance(rules[0], TradingRule)
        self.assertEqual(rules[0].min_price_increment, Decimal("0.1"))
        self.assertEqual(rules[0].min_base_amount_increment, Decimal("0.001"))

    def test_initialize_trading_pair_symbols(self):
        mock_markets = [
            {
                "symbol": "BTC-PERP",
                "market_address": "0xmarket_btc",
                "base_currency": "BTC",
                "quote_currency": "USD",
            }
        ]
        self.connector._initialize_trading_pair_symbols_from_exchange_info(mock_markets)
        self.assertIn("BTC-PERP", self.connector.market_name_to_address)
        self.assertEqual(
            self.connector.market_name_to_address["BTC-PERP"], "0xmarket_btc"
        )

    # ===== Balance Tests =====

    def test_update_balances(self):
        mock_overview = {
            "equity": "50000.00",
            "available_balance": "30000.00",
        }
        self.connector._api_get = AsyncMock(return_value=mock_overview)
        self.ev_loop.run_until_complete(self.connector._update_balances())
        self.assertEqual(
            self.connector._account_balances[CONSTANTS.CURRENCY], Decimal("50000.00")
        )
        self.assertEqual(
            self.connector._account_available_balances[CONSTANTS.CURRENCY],
            Decimal("30000.00"),
        )

    # ===== Position Tests =====

    def test_update_positions(self):
        mock_positions = [
            {
                "market": "BTC-PERP",
                "size": "1.5",
                "entry_price": "97000.00",
                "unrealized_pnl": "375.00",
                "leverage": "10",
            }
        ]
        self.connector._api_get = AsyncMock(return_value=mock_positions)
        self.connector.market_address_to_name = {}
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(
            return_value="BTC-USD"
        )
        self.ev_loop.run_until_complete(self.connector._update_positions())
        # Position should be tracked
        positions = self.connector._perpetual_trading.account_positions
        self.assertTrue(len(positions) > 0)

    def test_update_positions_empty(self):
        self.connector._api_get = AsyncMock(return_value=[])
        self.ev_loop.run_until_complete(self.connector._update_positions())
        positions = self.connector._perpetual_trading.account_positions
        self.assertEqual(len(positions), 0)

    # ===== Position Mode Tests =====

    def test_get_position_mode(self):
        mode = self.ev_loop.run_until_complete(self.connector._get_position_mode())
        self.assertEqual(mode, PositionMode.ONEWAY)

    def test_trading_pair_position_mode_set_oneway(self):
        success, msg = self.ev_loop.run_until_complete(
            self.connector._trading_pair_position_mode_set(PositionMode.ONEWAY, "BTC-USD")
        )
        self.assertTrue(success)

    def test_trading_pair_position_mode_set_hedge_fails(self):
        success, msg = self.ev_loop.run_until_complete(
            self.connector._trading_pair_position_mode_set(PositionMode.HEDGE, "BTC-USD")
        )
        self.assertFalse(success)
        self.assertIn("ONEWAY", msg)

    # ===== Order Status Tests =====

    def test_request_order_status(self):
        mock_order_data = {
            "order_id": "order_123",
            "status": "filled",
            "timestamp": time.time(),
            "client_order_id": "HBOT_test",
        }
        self.connector._api_get = AsyncMock(return_value=mock_order_data)

        tracked_order = MagicMock(spec=InFlightOrder)
        tracked_order.client_order_id = "HBOT_test"
        tracked_order.exchange_order_id = "order_123"
        tracked_order.trading_pair = "BTC-USD"

        order_update = self.ev_loop.run_until_complete(
            self.connector._request_order_status(tracked_order)
        )
        self.assertEqual(order_update.new_state, OrderState.FILLED)
        self.assertEqual(order_update.exchange_order_id, "order_123")

    # ===== Funding Tests =====

    def test_fetch_last_fee_payment(self):
        mock_funding = [
            {
                "market": "BTC-PERP",
                "payment": "5.25",
                "funding_rate": "0.0001",
                "timestamp": int(time.time()),
            }
        ]
        self.connector._api_get = AsyncMock(return_value=mock_funding)
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC-PERP")
        self.connector.market_name_to_address = {"BTC-PERP": "0xmarket_btc"}

        ts, rate, payment = self.ev_loop.run_until_complete(
            self.connector._fetch_last_fee_payment("BTC-USD")
        )
        self.assertGreater(ts, 0)
        self.assertEqual(rate, Decimal("0.0001"))
        self.assertEqual(payment, Decimal("5.25"))

    def test_fetch_last_fee_payment_empty(self):
        self.connector._api_get = AsyncMock(return_value=[])
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC-PERP")
        self.connector.market_name_to_address = {"BTC-PERP": "0xmarket_btc"}

        ts, rate, payment = self.ev_loop.run_until_complete(
            self.connector._fetch_last_fee_payment("BTC-USD")
        )
        self.assertEqual(ts, 0)
        self.assertEqual(rate, Decimal("-1"))

    # ===== Price Tests =====

    def test_get_last_traded_price(self):
        mock_prices = [
            {"symbol": "BTC-PERP", "mark_price": "97300.50", "market": "0xmarket_btc"}
        ]
        self.connector._api_get = AsyncMock(return_value=mock_prices)
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC-PERP")
        self.connector.market_name_to_address = {"BTC-PERP": "0xmarket_btc"}

        price = self.ev_loop.run_until_complete(
            self.connector._get_last_traded_price("BTC-USD")
        )
        self.assertAlmostEqual(price, 97300.50)

    def test_get_all_pairs_prices(self):
        mock_prices = [
            {"symbol": "BTC-PERP", "mark_price": "97300.50"},
            {"symbol": "ETH-PERP", "mark_price": "3500.00"},
        ]
        self.connector._api_get = AsyncMock(return_value=mock_prices)
        self.connector.market_address_to_name = {}

        prices = self.ev_loop.run_until_complete(self.connector.get_all_pairs_prices())
        self.assertEqual(len(prices), 2)
        self.assertEqual(prices[0]["symbol"], "BTC-PERP")

    # ===== Order Processing Tests =====

    def test_process_order_message(self):
        tracked_order = MagicMock(spec=InFlightOrder)
        tracked_order.trading_pair = "BTC-USD"
        tracked_order.client_order_id = "HBOT_001"
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_updatable_orders = {"HBOT_001": tracked_order}

        order_msg = {
            "client_order_id": "HBOT_001",
            "order_id": "exchange_001",
            "status": "filled",
            "timestamp": time.time(),
        }
        self.connector._process_order_message(order_msg)
        self.connector._order_tracker.process_order_update.assert_called_once()

    def test_process_order_message_unknown_order(self):
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_updatable_orders = {}

        order_msg = {
            "client_order_id": "UNKNOWN_001",
            "order_id": "exchange_001",
            "status": "filled",
        }
        # Should not raise, just log debug
        self.connector._process_order_message(order_msg)
        self.connector._order_tracker.process_order_update.assert_not_called()

    # ===== Trade Processing Tests =====

    def test_process_trade_rs_event_message(self):
        fillable_order = MagicMock(spec=InFlightOrder)
        fillable_order.quote_asset = "USD"
        fillable_order.client_order_id = "HBOT_001"
        fillable_order.trading_pair = "BTC-USD"

        self.connector._order_tracker = MagicMock()

        order_fill = {
            "order_id": "exchange_001",
            "trade_id": "trade_001",
            "price": "97250.00",
            "size": "0.5",
            "fee": "4.86",
            "side": "buy",
            "timestamp": time.time(),
        }
        all_fillable = {"exchange_001": fillable_order}
        self.connector._process_trade_rs_event_message(order_fill, all_fillable)
        self.connector._order_tracker.process_trade_update.assert_called_once()

    # ===== Leverage Tests =====

    def test_set_trading_pair_leverage(self):
        success, msg = self.ev_loop.run_until_complete(
            self.connector._set_trading_pair_leverage("BTC-USD", 10)
        )
        self.assertTrue(success)

    def test_quantize_order_price(self):
        price = self.connector.quantize_order_price("BTC-USD", Decimal("97253.456789"))
        self.assertIsInstance(price, Decimal)


if __name__ == "__main__":
    unittest.main()
