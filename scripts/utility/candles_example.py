from typing import Dict

import pandas as pd
import pandas_ta as ta  # noqa: F401

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class CandlesExample(ScriptStrategyBase):
    """
    This is a strategy that shows how to use the new Candlestick component.
    It acquires data from both Binance spot and Binance perpetuals to initialize three different timeframes
    of candlesticks.
    The candlesticks are then displayed in the status, which is coded using a custom format status that
    includes technical indicators.
    This strategy serves as a clear example for other users on how to effectively utilize candlesticks in their own
    trading strategies by utilizing the new Candlestick component. The integration of multiple timeframes and technical
    indicators provides a comprehensive view of market trends and conditions, making this strategy a valuable tool for
    informed trading decisions.
    """
    # Available intervals: |1s|1m|3m|5m|15m|30m|1h|2h|4h|6h|8h|12h|1d|3d|1w|1M|
    # Is possible to use the Candles Factory to create the candlestick that you want, and then you have to start it.
    # Also, you can use the class directly like BinancePerpetualsCandles(trading_pair, interval, max_records), but
    # this approach is better if you want to initialize multiple candles with a list or dict of configurations.
    eth_1m_candles = CandlesFactory.get_candle(CandlesConfig(connector="binance", trading_pair="ETH-USDT", interval="1m", max_records=1000))
    eth_1h_candles = CandlesFactory.get_candle(CandlesConfig(connector="binance", trading_pair="ETH-USDT", interval="1h", max_records=1000))
    eth_1w_candles = CandlesFactory.get_candle(CandlesConfig(connector="binance", trading_pair="ETH-USDT", interval="1w", max_records=200))

    # The markets are the connectors that you can use to execute all the methods of the scripts strategy base
    # The candlesticks are just a component that provides the information of the candlesticks
    markets = {"binance_paper_trade": {"SOL-USDT"}}

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        # Is necessary to start the Candles Feed.
        super().__init__(connectors)
        self.eth_1m_candles.start()
        self.eth_1h_candles.start()
        self.eth_1w_candles.start()

    @property
    def all_candles_ready(self):
        """
        Checks if the candlesticks are full.
        :return:
        """
        return all([self.eth_1h_candles.ready, self.eth_1m_candles.ready, self.eth_1w_candles.ready])

    def on_tick(self):
        pass

    async def on_stop(self):
        """
        Without this functionality, the network iterator will continue running forever after stopping the strategy
        That's why is necessary to introduce this new feature to make a custom stop with the strategy.
        :return:
        """
        self.eth_1m_candles.stop()
        self.eth_1h_candles.stop()
        self.eth_1w_candles.stop()

    def format_status(self) -> str:
        """
        Displays the three candlesticks involved in the script with RSI, BBANDS and EMA.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        if self.all_candles_ready:
            lines.extend(["\n############################################ Market Data ############################################\n"])
            for candles in [self.eth_1w_candles, self.eth_1m_candles, self.eth_1h_candles]:
                candles_df = candles.candles_df
                # Let's add some technical indicators
                candles_df.ta.rsi(length=14, append=True)
                candles_df.ta.bbands(length=20, std=2, append=True)
                candles_df.ta.ema(length=14, offset=None, append=True)
                candles_df["timestamp"] = pd.to_datetime(candles_df["timestamp"], unit="ms")
                lines.extend([f"Candles: {candles.name} | Interval: {candles.interval}"])
                lines.extend(["    " + line for line in candles_df.tail().to_string(index=False).split("\n")])
                lines.extend(["\n-----------------------------------------------------------------------------------------------------------\n"])
        else:
            lines.extend(["", "  No data collected."])

        return "\n".join(lines)
