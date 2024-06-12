from typing import Dict

import pandas as pd
import pandas_ta as ta  # noqa: F401

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig, CandlesFactory
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class StreamCandles(ScriptStrategyBase):
    """
    This script is a simple example of how to use the Candles Factory to create a candlestick and start it.
    """
    # Available intervals: |1s|1m|3m|5m|15m|30m|1h|2h|4h|6h|8h|12h|1d|3d|1w|1M|
    # Is possible to use the Candles Factory to create the candlestick that you want, and then you have to start it.
    # Also, you can use the class directly like BinancePerpetualsCandles(trading_pair, interval, max_records), but
    # this approach is better if you want to initialize multiple candles with a list or dict of configurations.
    candles = CandlesFactory.get_candle(CandlesConfig(connector="binance_perpetual",
                                                      trading_pair="ETH-USDT",
                                                      interval="1m",
                                                      max_records=200))

    # The markets are the connectors that you can use to execute all the methods of the scripts strategy base
    # The candlesticks are just a component that provides the information of the candlesticks
    markets = {"binance_paper_trade": {"SOL-USDT"}}

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        # Is necessary to start the Candles Feed.
        super().__init__(connectors)
        self.candles.start()

    def on_tick(self):
        pass

    def on_stop(self):
        """
        Without this functionality, the network iterator will continue running forever after stopping the strategy
        That's why is necessary to introduce this new feature to make a custom stop with the strategy.
        :return:
        """
        self.candles.stop()

    def format_status(self) -> str:
        """
        Displays the three candlesticks involved in the script with RSI, BBANDS and EMA.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        lines.extend(["\n############################################ Market Data ############################################\n"])
        candles_df = self.candles.candles_df
        # Let's add some technical indicators
        candles_df.ta.ema(length=14, offset=None, append=True)
        candles_df["timestamp"] = pd.to_datetime(candles_df["timestamp"], unit="s")
        lines.extend([f"Candles: {self.candles.name} | Interval: {self.candles.interval}"])
        lines.extend(["    " + line for line in candles_df.tail().to_string(index=False).split("\n")])
        lines.extend(["\n-----------------------------------------------------------------------------------------------------------\n"])

        return "\n".join(lines)
