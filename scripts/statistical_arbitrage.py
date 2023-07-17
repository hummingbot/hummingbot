from decimal import Decimal

import pandas as pd
import pandas_ta as ta

from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.strategy.directional_strategy_base import DirectionalStrategyBase


class StatisticalArbitrageLeft(DirectionalStrategyBase):
    """
    BotCamp Cohort #5 July 2023
    Design Template: https://github.com/hummingbot/hummingbot-botcamp/issues/48

    Description:
    Statistical Arbitrage strategy implementation based on the DirectionalStrategyBase.
    This strategy execute trades based on the Z-score values.
    This strategy is divided into a left and right side code.
    Left side code is statistical_arbitrage_left.py.
    Right side code is statistical_arbitrage_right.py.
    This code the left side of this strategy
    When z-score indicates an entry signal. the left side will execute a long position and right side will execute a short position.
    When z-score indicates an exit signal. the left side will execute a short position and right side will execute a long position.
    """
    directional_strategy_name: str = "statistical_arbitrage_left"
    # Define the trading pair and exchange that we want to use and the csv where we are going to store the entries
    trading_pair: str = "ETH-USDT"  # left side trading pair
    trading_pair_2: str = "BTC-USDT"  # right side trading pair
    exchange: str = "binance_perpetual"
    order_amount_usd = Decimal("10")
    leverage = 10
    length = 100

    # Configure the parameters for the position
    zscore_entry: int = -2
    zscore_entry_sl: int = -3
    zscore_exit: int = 2
    zscore_exit_sl: int = 3

    candles = [
        CandlesFactory.get_candle(connector=exchange,
                                  trading_pair=trading_pair,
                                  interval="1h", max_records=1000),
        CandlesFactory.get_candle(connector=exchange,
                                  trading_pair=trading_pair_2,
                                  interval="1h", max_records=1000),
    ]
    markets = {exchange: {trading_pair, trading_pair_2}}

    def get_signal(self):

        candles_df = self.get_processed_df()
        z_score = candles_df.iat[-1, -1]

        # all execution are only on the left side trading pair
        if z_score < self.zscore_entry or z_score > self.zscore_exit_sl:
            return 1  # long 1
        elif z_score < self.zscore_entry_sl or z_score > self.zscore_exit:
            return -1  # stop loss long  -1
        else:
            return 0

    def get_processed_df(self):

        candles_df_1 = self.candles[0].candles_df
        candles_df_2 = self.candles[1].candles_df

        # calculate the spread and z-score based on the candles of 2 trading pairs
        df = pd.merge(candles_df_1, candles_df_2, on="timestamp", how='inner', suffixes=('', '_2'))
        hedge_ratio = df["close"].tail(self.length).mean() / df["close_2"].tail(self.length).mean()

        df["spread"] = df["close"] - (df["close_2"] * hedge_ratio)
        df["z_score"] = ta.zscore(df["spread"], length=self.length)

        return df

    def market_data_extra_info(self):
        """
        Provides additional information about the market data to the format status.
        Returns:
            List[str]: A list of formatted strings containing market data information.
        """
        lines = []
        columns_to_show = ["timestamp", "open", "low", "high", "close", "volume", "z_score", "close_2"]
        candles_df = self.get_processed_df()
        lines.extend([f"Candles: {self.candles[0].name} | Interval: {self.candles[0].interval}\n"])
        lines.extend(self.candles_formatted_list(candles_df, columns_to_show))
        return lines
