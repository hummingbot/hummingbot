from decimal import Decimal

from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy.directional_strategy_base import DirectionalStrategyBase


class MacdBB(DirectionalStrategyBase):
    """
    MacdBB strategy implementation based on the DirectionalStrategyBase.

    This strategy combines the MACD (Moving Average Convergence Divergence) and Bollinger Bands indicators to generate
    trading signals and execute trades based on the indicator values. It defines the specific parameters and
    configurations for the MacdBB strategy.

    Parameters:
        directional_strategy_name (str): The name of the strategy.
        trading_pair (str): The trading pair to be traded.
        exchange (str): The exchange to be used for trading.
        order_amount_usd (Decimal): The amount of the order in USD.
        leverage (int): The leverage to be used for trading.

    Position Parameters:
        stop_loss (float): The stop-loss percentage for the position.
        take_profit (float): The take-profit percentage for the position.
        time_limit (int): The time limit for the position in seconds.
        trailing_stop_activation_delta (float): The activation delta for the trailing stop.
        trailing_stop_trailing_delta (float): The trailing delta for the trailing stop.

    Candlestick Configuration:
        candles (List[CandlesBase]): The list of candlesticks used for generating signals.

    Markets:
        A dictionary specifying the markets and trading pairs for the strategy.

    Inherits from:
        DirectionalStrategyBase: Base class for creating directional strategies using the PositionExecutor.
    """
    directional_strategy_name: str = "MACD_BB"
    # Define the trading pair and exchange that we want to use and the csv where we are going to store the entries
    trading_pair: str = "BTC-USDT"
    exchange: str = "binance_perpetual"
    order_amount_usd = Decimal("40")
    leverage = 10

    # Configure the parameters for the position
    stop_loss: float = 0.0075
    take_profit: float = 0.015
    time_limit: int = 60 * 55
    trailing_stop_activation_delta = 0.003
    trailing_stop_trailing_delta = 0.0007

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
        macdh = last_candle["MACDh_21_42_9"]
        macd = last_candle["MACD_21_42_9"]
        if bbp < 0.4 and macdh > 0 and macd < 0:
            signal_value = 1
        elif bbp > 0.6 and macdh < 0 and macd > 0:
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
        candles_df.ta.bbands(length=100, append=True)
        candles_df.ta.macd(fast=21, slow=42, signal=9, append=True)
        return candles_df

    def market_data_extra_info(self):
        """
        Provides additional information about the market data.
        Returns:
            List[str]: A list of formatted strings containing market data information.
        """
        lines = []
        columns_to_show = ["timestamp", "open", "low", "high", "close", "volume", "BBP_100_2.0", "MACDh_21_42_9", "MACD_21_42_9"]
        candles_df = self.get_processed_df()
        lines.extend([f"Candles: {self.candles[0].name} | Interval: {self.candles[0].interval}\n"])
        lines.extend(self.candles_formatted_list(candles_df, columns_to_show))
        return lines
