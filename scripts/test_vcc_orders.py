"""
Test script for WEEX VCC-USDT order placement
"""
from decimal import Decimal

from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class TestVCCOrders(ScriptStrategyBase):
    """
    Simple script to test VCC-USDT order placement on WEEX
    """
    markets = {"weex": {"VCC-USDT"}}

    def __init__(self, connectors):
        super().__init__(connectors)
        self.test_executed = False

    def on_tick(self):
        if not self.test_executed:
            self.logger().info("Testing WEEX order placement...")

            # Get current mid price
            mid_price = self.connectors["weex"].get_mid_price("VCC-USDT")
            self.logger().info(f"Current VCC-USDT mid price: {mid_price}")

            # Place a buy order 50% below mid price (won't fill)
            test_price = mid_price * Decimal("0.5")
            test_amount = Decimal("100")  # 100 VCC

            self.logger().info(f"Placing test buy order: {test_amount} VCC at {test_price} USDT")

            buy_order = self.buy(
                connector_name="weex",
                trading_pair="VCC-USDT",
                amount=test_amount,
                order_type="limit",
                price=test_price
            )

            if buy_order:
                self.logger().info(f"✓ Order placed successfully! Order ID: {buy_order}")
            else:
                self.logger().error("✗ Order placement failed!")

            self.test_executed = True

    def on_status(self):
        if self.test_executed:
            return "Test order placed. Check logs and use 'cancel' command to cancel the order."
        else:
            return "Waiting to place test order..."
