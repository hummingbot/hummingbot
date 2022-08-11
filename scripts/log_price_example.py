from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class LogPricesExample(ScriptStrategyBase):
    """
    This example shows how to get the ask and bid of a market and log it to the console.
    """
    markets = {
        "gate_io_paper_trade": {"ETH-USDT"},
        "kucoin_paper_trade": {"ETH-USDT"},
        "binance_paper_trade": {"ETH-USDT"}
    }

    def on_tick(self):
        for connector_name, connector in self.connectors.items():
            self.logger().info(f"Connector: {connector_name}")
            self.logger().info(f"Best Ask: {connector.get_price('ETH-USDT', True)}")
            self.logger().info(f"Best Bid: {connector.get_price('ETH-USDT', False)}")
