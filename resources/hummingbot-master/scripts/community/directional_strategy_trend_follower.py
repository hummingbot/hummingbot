from decimal import Decimal

import pandas_ta as ta  # noqa: F401

from hummingbot.core.data_type.common import OrderType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy.directional_strategy_base import DirectionalStrategyBase


class TrendFollowingStrategy(DirectionalStrategyBase):
    directional_strategy_name = "trend_following"
    trading_pair = "DOGE-USDT"
    exchange = "binance_perpetual"
    order_amount_usd = Decimal("40")
    leverage = 10

    # Configure the parameters for the position
    stop_loss: float = 0.01
    take_profit: float = 0.05
    time_limit: int = 60 * 60 * 3
    open_order_type = OrderType.MARKET
    take_profit_order_type: OrderType = OrderType.MARKET
    trailing_stop_activation_delta = 0.01
    trailing_stop_trailing_delta = 0.003
    candles = [CandlesFactory.get_candle(CandlesConfig(connector=exchange, trading_pair=trading_pair, interval="3m", max_records=1000))]
    markets = {exchange: {trading_pair}}

    def get_signal(self):
        """
        Generates the trading signal based on the MACD and Bollinger Bands indicators.
        Returns:
            int: The trading signal (-1 for sell, 0 for hold, 1 for buy).
        """
        candles_df = self.get_processed_df()
        last_candle = candles_df.iloc[-1]
        bbp = last_candle["BBP_100_2.0"]
        sma_21 = last_candle["SMA_21"]
        sma_200 = last_candle["SMA_200"]
        trend = sma_21 > sma_200
        filter = (bbp > 0.35) and (bbp < 0.65)

        if trend and filter:
            signal_value = 1
        elif not trend and filter:
            signal_value = -1
        else:
            signal_value = 0
        return signal_value

    def get_processed_df(self):
        """
        Retrieves the processed dataframe with MACD and Bollinger Bands values.
        Returns:
            pd.DataFrame: The processed dataframe with MACD and Bollinger Bands values.
        """
        candles_df = self.candles[0].candles_df
        candles_df.ta.sma(length=21, append=True)
        candles_df.ta.sma(length=200, append=True)
        candles_df.ta.bbands(length=100, append=True)
        return candles_df

    def market_data_extra_info(self):
        """
        Provides additional information about the market data.
        Returns:
            List[str]: A list of formatted strings containing market data information.
        """
        lines = []
        columns_to_show = ["timestamp", "open", "low", "high", "close", "volume", "BBP_100_2.0", "SMA_21", "SMA_200"]
        candles_df = self.get_processed_df()
        lines.extend([f"Candles: {self.candles[0].name} | Interval: {self.candles[0].interval}\n"])
        lines.extend(self.candles_formatted_list(candles_df, columns_to_show))
        return lines
