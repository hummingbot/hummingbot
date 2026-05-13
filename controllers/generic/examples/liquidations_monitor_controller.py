from typing import List

from pydantic import Field

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.core.data_type.common import MarketDict
from hummingbot.data_feed.liquidations_feed.liquidations_factory import LiquidationsConfig, LiquidationsFactory
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.models.executor_actions import ExecutorAction


class LiquidationsMonitorControllerConfig(ControllerConfigBase):
    controller_name: str = "examples.liquidations_monitor_controller"
    exchange: str = Field(default="binance_paper_trade")
    trading_pair: str = Field(default="BTC-USDT")
    liquidations_trading_pairs: list = Field(default=["BTC-USDT", "1000PEPE-USDT", "1000BONK-USDT", "HBAR-USDT"])
    max_retention_seconds: int = Field(default=10)

    def update_markets(self, markets: MarketDict) -> MarketDict:
        markets[self.exchange] = markets.get(self.exchange, set()) | {self.trading_pair}
        return markets


class LiquidationsMonitorController(ControllerBase):
    def __init__(self, config: LiquidationsMonitorControllerConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config

        # Initialize liquidations feed
        self.binance_liquidations_config = LiquidationsConfig(
            connector="binance",  # the source for liquidation data (currently only binance is supported)
            max_retention_seconds=self.config.max_retention_seconds,  # how many seconds the data should be stored
            trading_pairs=self.config.liquidations_trading_pairs
        )
        self.binance_liquidations_feed = LiquidationsFactory.get_liquidations_feed(self.binance_liquidations_config)
        self.binance_liquidations_feed.start()

    async def update_processed_data(self):
        liquidations_data = {
            "feed_ready": self.binance_liquidations_feed.ready,
            "trading_pairs": self.config.liquidations_trading_pairs
        }

        if self.binance_liquidations_feed.ready:
            try:
                # Get combined liquidations dataframe
                liquidations_data["combined_df"] = self.binance_liquidations_feed.liquidations_df()

                # Get individual trading pair dataframes
                liquidations_data["individual_dfs"] = {}
                for trading_pair in self.config.liquidations_trading_pairs:
                    liquidations_data["individual_dfs"][trading_pair] = self.binance_liquidations_feed.liquidations_df(trading_pair)
            except Exception as e:
                self.logger().error(f"Error getting liquidations data: {e}")
                liquidations_data["error"] = str(e)

        self.processed_data = liquidations_data

    def determine_executor_actions(self) -> list[ExecutorAction]:
        # This controller is for monitoring only, no trading actions
        return []

    def to_format_status(self) -> List[str]:
        lines = []
        lines.extend(["", "LIQUIDATIONS MONITOR"])
        lines.extend(["=" * 50])

        if not self.binance_liquidations_feed.ready:
            lines.append("Feed not ready yet!")
        else:
            try:
                # Combined liquidations
                lines.append("Combined liquidations:")
                combined_df = self.binance_liquidations_feed.liquidations_df().tail(10)
                lines.extend([format_df_for_printout(df=combined_df, table_format="psql")])
                lines.append("")
                lines.append("")

                # Individual trading pairs
                for trading_pair in self.binance_liquidations_config.trading_pairs:
                    lines.append("Liquidations for trading pair: {}".format(trading_pair))
                    pair_df = self.binance_liquidations_feed.liquidations_df(trading_pair).tail(5)
                    lines.extend([format_df_for_printout(df=pair_df, table_format="psql")])
                    lines.append("")
            except Exception as e:
                lines.append(f"Error displaying liquidations data: {e}")

        return lines

    async def stop(self):
        """Clean shutdown of the liquidations feed"""
        if hasattr(self, 'binance_liquidations_feed'):
            self.binance_liquidations_feed.stop()
        await super().stop()
