import os

from pydantic import Field

from hummingbot.core.data_type.common import MarketDict
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase


class LogPricesExampleConfig(StrategyV2ConfigBase):
    script_file_name: str = os.path.basename(__file__)
    exchanges: list = Field(default=["binance_paper_trade", "kucoin_paper_trade", "gate_io_paper_trade"])
    trading_pair: str = Field(default="ETH-USDT")

    def update_markets(self, markets: MarketDict) -> MarketDict:
        # Add the trading pair to all exchanges
        for exchange in self.exchanges:
            markets[exchange] = markets.get(exchange, set()) | {self.trading_pair}
        return markets


class LogPricesExample(StrategyV2Base):
    """
    This example shows how to get the ask and bid of a market and log it to the console.
    """

    def __init__(self, connectors, config: LogPricesExampleConfig):
        super().__init__(connectors, config)
        self.config = config

    def on_tick(self):
        for connector_name, connector in self.connectors.items():
            self.logger().info(f"Connector: {connector_name}")
            self.logger().info(f"Best ask: {connector.get_price(self.config.trading_pair, True)}")
            self.logger().info(f"Best bid: {connector.get_price(self.config.trading_pair, False)}")
            self.logger().info(f"Mid price: {connector.get_mid_price(self.config.trading_pair)}")
