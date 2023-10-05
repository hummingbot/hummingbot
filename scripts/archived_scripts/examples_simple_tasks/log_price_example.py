from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class LogPricesExample(ScriptStrategyBase):
    """
    This example shows how to get the ask and bid of a market and log it to the console.
    """
    markets = {
        "binance_paper_trade": {"ETH-USDT"},
        "kucoin_paper_trade": {"ETH-USDT"},
        "gate_io_paper_trade": {"ETH-USDT"}
    }

    def on_tick(self):
        for connector_name, connector in self.connectors.items():
            self.logger().info(f"Connector: {connector_name}")
            self.logger().info(f"Best ask: {connector.get_price('ETH-USDT', True)}")
            self.logger().info(f"Best bid: {connector.get_price('ETH-USDT', False)}")
            self.logger().info(f"Mid price: {connector.get_mid_price('ETH-USDT')}")
