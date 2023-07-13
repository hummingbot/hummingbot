from decimal import Decimal

import pandas as pd
import pandas_ta as ta

from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.strategy.directional_strategy_base import DirectionalStrategyBase


class StatisticalArbitrageRight(DirectionalStrategyBase):
    """
        BotCamp Cohort #5 July 2023
        Design Template: https://github.com/hummingbot/hummingbot-botcamp/issues/48

        Description:
        Statistical Arbitrage strategy implementation based on the DirectionalStrategyBase.
        This strategy execute trades based on the Z-score values.
        This strategy is divided into a left and right side code.
        Left side code is statistical_arbitrage_left.py.
        Right side code is statistical_arbitrage_right.py.
        This code the right side of this strategy
        When z-score indicates an entry signal. the left side will execute a long position and right side will execute a short position.
        When z-score indicates an exit signal. the left side will execute a short position and right side will execute a long position.
        """
    directional_strategy_name: str = "statistical_arbitrage_right"
    # Define the trading pair and exchange that we want to use and the csv where we are going to store the entries
    trading_pair_left: str = "ETH-USDT"  # left side trading pair
    trading_pair: str = "BTC-USDT"  # right side trading pair
    exchange: str = "binance_perpetual"
    order_amount_usd = Decimal("15")
    leverage = 10
    length = 100

    # Configure the parameters for the position
    zscore_entry: int = -2
    zscore_entry_sl: int = -3
    zscore_exit: int = 2
    zscore_exit_sl: int = 3

    # stop_loss: float = 0.0075
    # take_profit: float = 0.015
    time_limit: int = 60 * 55
    trailing_stop_activation_delta = 0.01
    trailing_stop_trailing_delta = 0.01

    candles = [
        CandlesFactory.get_candle(connector=exchange,
                                  trading_pair=trading_pair_left,
                                  interval="1h", max_records=300),
        CandlesFactory.get_candle(connector=exchange,
                                  trading_pair=trading_pair,
                                  interval="1h", max_records=300),
    ]
    markets = {exchange: {trading_pair}}

    def get_signal(self):

        candles_df = self.get_processed_df()
        z_score = candles_df.iat[-1, -1]

        if z_score < self.zscore_entry:
            return -1  # short -1
        elif z_score < self.zscore_entry_sl:
            return 1  # stop loss short 1
        elif z_score > self.zscore_exit:
            return 1  # long 1
        elif z_score > self.zscore_exit_sl:
            return -1  # stop loss long -1
        else:
            return 0

    def get_processed_df(self):

        candles_df_1 = self.candles[0].candles_df
        candles_df_2 = self.candles[1].candles_df

        # calculate the spread and z-score based on the candles of 2 trading pairs
        df = pd.merge(candles_df_1, candles_df_2, on="timestamp", how='inner', suffixes=('_left', ''))
        hedge_ratio = df["close_left"].tail(self.length).mean() / df["close"].tail(self.length).mean()

        df["spread"] = df["close_left"] - (df["close"] * hedge_ratio)
        df["z_score"] = ta.zscore(df["spread"], length=self.length)

        return df

    def market_data_extra_info(self):
        """
        Provides additional information about the market data to the format status.
        Returns:
            List[str]: A list of formatted strings containing market data information.
        """
        lines = []
        columns_to_show = ["timestamp", "open", "low", "high", "close", "volume", "z_score"]
        candles_df = self.get_processed_df()
        lines.extend([f"Candles: {self.candles[0].name} | Interval: {self.candles[0].interval}\n"])
        lines.extend(self.candles_formatted_list(candles_df, columns_to_show))
        return lines
