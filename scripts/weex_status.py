"""
WEEX Connector Status Check
"""
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class WeexStatus(ScriptStrategyBase):
    markets = {"weex": {"VCC-USDT"}}

    def on_tick(self):
        weex = self.connectors["weex"]
        self.logger().info(f"WEEX Ready: {weex.ready}")
        self.logger().info(f"WEEX Trading Rules: {len(weex.trading_rules)}")

        if weex.ready:
            try:
                mid_price = weex.get_mid_price("VCC-USDT")
                self.logger().info(f"✓ VCC-USDT Mid Price: {mid_price}")
            except Exception as e:
                self.logger().error(f"✗ Error getting price: {e}")

        # Stop after first check
        self.stop()

    def on_status(self):
        return "Checking WEEX connector status..."
