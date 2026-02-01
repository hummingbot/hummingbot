"""
Quick test to check WEEX connector readiness
"""
import os
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class TestWeexReadyConfig(BaseClientModel):
    script_file_name: str = os.path.basename(__file__)
    exchange: str = Field(default="weex")
    trading_pair: str = Field(default="VCC-USDT")


class TestWeexReady(ScriptStrategyBase):
    """Test WEEX connector readiness"""

    markets = {"weex": {"VCC-USDT"}}

    @classmethod
    def init_markets(cls, config: TestWeexReadyConfig):
        cls.markets = {config.exchange: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: TestWeexReadyConfig):
        super().__init__(connectors)
        self.config = config
        self._checked = False
        # Force ready_to_trade to True to bypass connector ready check
        self.ready_to_trade = True

    def on_tick(self):
        if self._checked:
            return

        weex = self.connectors.get("weex")
        if not weex:
            self.logger().error("❌ WEEX connector not found!")
            self.stop()
            return

        self.logger().info(f"✓ WEEX connector found: {weex}")
        self.logger().info(f"  - Ready: {weex.ready}")
        self.logger().info(f"  - Trading rules count: {len(weex.trading_rules)}")
        self.logger().info(f"  - Trading pairs: {list(weex.trading_pairs) if hasattr(weex, 'trading_pairs') else 'N/A'}")

        if weex.ready:
            self.logger().info("✓ WEEX is READY!")
            try:
                mid_price = weex.get_mid_price("VCC-USDT")
                self.logger().info(f"✓ Mid price: {mid_price}")
            except Exception as e:
                self.logger().error(f"❌ Error getting mid price: {e}")
        else:
            self.logger().warning("⚠️  WEEX not ready yet, checking details...")
            self.logger().info(f"  - _trading_pair_symbol_map: {len(weex._trading_pair_symbol_map) if hasattr(weex, '_trading_pair_symbol_map') else 'N/A'}")
            if hasattr(weex, 'status_dict'):
                for key, val in weex.status_dict.items():
                    self.logger().info(f"  - {key}: {val}")

        self._checked = True
        # Stop after first check
        self.stop()

    def format_status(self) -> str:
        return "Testing WEEX connector readiness..."
