from typing import Dict

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.data_feed.liquidations_feed.liquidations_factory import LiquidationsConfig, LiquidationsFactory
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class LiquidationsExample(ScriptStrategyBase):
    markets = {"binance_paper_trade": ["BTC-USDT"]}

    binance_liquidations_config = LiquidationsConfig(
        connector="binance",  # the source for liquidation data (currently only binance is supported)
        max_retention_seconds=10,  # how many seconds the data should be stored (default is 60s)
        trading_pairs=["BTC-USDT", "1000PEPE-USDT", "1000BONK-USDT", "HBAR-USDT"]
        # optional, unset/none = all liquidations
    )
    binance_liquidations_feed = LiquidationsFactory.get_liquidations_feed(binance_liquidations_config)

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.binance_liquidations_feed.start()

    async def on_stop(self):
        self.binance_liquidations_feed.stop()

    def on_tick(self):
        if not self.binance_liquidations_feed.ready:
            self.logger().info("Feed not ready yet!")

    def format_status(self) -> str:
        lines = []

        if not self.binance_liquidations_feed.ready:
            lines.append("Feed not ready yet!")
        else:
            # You can get all the liquidations in a single dataframe
            lines.append("Combined liquidations:")
            lines.extend([format_df_for_printout(df=self.binance_liquidations_feed.liquidations_df().tail(10),
                                                 table_format="psql")])
            lines.append("")
            lines.append("")

            # Or you can get a dataframe for a single trading-pair
            for trading_pair in self.binance_liquidations_config.trading_pairs:
                lines.append("Liquidations for trading pair: {}".format(trading_pair))
                lines.extend(
                    [format_df_for_printout(df=self.binance_liquidations_feed.liquidations_df(trading_pair).tail(5),
                                            table_format="psql")])

        return "\n".join(lines)
