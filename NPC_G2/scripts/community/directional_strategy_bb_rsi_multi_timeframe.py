from decimal import Decimal

from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy.directional_strategy_base import DirectionalStrategyBase


class MultiTimeframeBBRSI(DirectionalStrategyBase):
    """
    MultiTimeframeBBRSI strategy implementation based on the DirectionalStrategyBase.

    This strategy combines multiple timeframes of Bollinger Bands (BB) and Relative Strength Index (RSI) indicators to
    generate trading signals and execute trades based on the composed signal value. It defines the specific parameters
    and configurations for the MultiTimeframeBBRSI strategy.

    Parameters:
        directional_strategy_name (str): The name of the strategy.
        trading_pair (str): The trading pair to be traded.
        exchange (str): The exchange to be used for trading.
        order_amount_usd (Decimal): The amount of the order in USD.
        leverage (int): The leverage to be used for trading.

    Position Parameters:
        stop_loss (float): The stop-loss percentage for the position.
        take_profit (float): The take-profit percentage for the position.
        time_limit (int or None): The time limit for the position in seconds. Set to `None` for no time limit.
        trailing_stop_activation_delta (float): The activation delta for the trailing stop.
        trailing_stop_trailing_delta (float): The trailing delta for the trailing stop.

    Candlestick Configuration:
        candles (List[CandlesBase]): The list of candlesticks used for generating signals.

    Markets:
        A dictionary specifying the markets and trading pairs for the strategy.

    Inherits from:
        DirectionalStrategyBase: Base class for creating directional strategies using the PositionExecutor.
    """
    directional_strategy_name: str = "bb_rsi_multi_timeframe"
    # Define the trading pair and exchange that we want to use and the csv where we are going to store the entries
    trading_pair: str = "ETH-USDT"
    exchange: str = "binance_perpetual"
    order_amount_usd = Decimal("40")
    leverage = 10

    # Configure the parameters for the position
    stop_loss: float = 0.0075
    take_profit: float = 0.015
    time_limit: int = None
    trailing_stop_activation_delta = 0.004
    trailing_stop_trailing_delta = 0.001
    CandlesConfig(connector=exchange, trading_pair=trading_pair, interval="3m", max_records=1000)
    candles = [
        CandlesFactory.get_candle(CandlesConfig(connector=exchange, trading_pair=trading_pair, interval="1m", max_records=1000)),
        CandlesFactory.get_candle(CandlesConfig(connector=exchange, trading_pair=trading_pair, interval="3m", max_records=1000)),
    ]
    markets = {exchange: {trading_pair}}

    def get_signal(self):
        """
        Generates the trading signal based on the composed signal value from multiple timeframes.
        Returns:
            int: The trading signal (-1 for sell, 0 for hold, 1 for buy).
        """
        signals = []
        for candle in self.candles:
            candles_df = self.get_processed_df(candle.candles_df)
            last_row = candles_df.iloc[-1]
            # We are going to normalize the values of the signals between -1 and 1.
            # -1 --> short | 1 --> long, so in the normalization we also need to switch side by changing the sign
            sma_rsi_normalized = -1 * (last_row["RSI_21_SMA_10"].item() - 50) / 50
            bb_percentage_normalized = -1 * (last_row["BBP_21_2.0"].item() - 0.5) / 0.5
            # we assume that the weights of sma of rsi and bb are equal
            signal_value = (sma_rsi_normalized + bb_percentage_normalized) / 2
            signals.append(signal_value)
        # Here we have a list with the values of the signals for each candle
        # The idea is that you can define rules between the signal values of multiple trading pairs or timeframes
        # In this example, we are going to prioritize the short term signal, so the weight of the 1m candle
        # is going to be 0.7 and the weight of the 3m candle 0.3
        composed_signal_value = 0.7 * signals[0] + 0.3 * signals[1]
        # Here we are applying thresholds to the composed signal value
        if composed_signal_value > 0.5:
            return 1
        elif composed_signal_value < -0.5:
            return -1
        else:
            return 0

    @staticmethod
    def get_processed_df(candles):
        """
        Retrieves the processed dataframe with Bollinger Bands and RSI values for a specific candlestick.
        Args:
            candles (pd.DataFrame): The raw candlestick dataframe.
        Returns:
            pd.DataFrame: The processed dataframe with Bollinger Bands and RSI values.
        """
        candles_df = candles.copy()
        # Let's add some technical indicators
        candles_df.ta.bbands(length=21, append=True)
        candles_df.ta.rsi(length=21, append=True)
        candles_df.ta.sma(length=10, close="RSI_21", prefix="RSI_21", append=True)
        return candles_df

    def market_data_extra_info(self):
        """
        Provides additional information about the market data for each candlestick.
        Returns:
            List[str]: A list of formatted strings containing market data information.
        """
        lines = []
        columns_to_show = ["timestamp", "open", "low", "high", "close", "volume", "RSI_21_SMA_10", "BBP_21_2.0"]
        for candle in self.candles:
            candles_df = self.get_processed_df(candle.candles_df)
            lines.extend([f"Candles: {candle.name} | Interval: {candle.interval}\n"])
            lines.extend(self.candles_formatted_list(candles_df, columns_to_show))
        return lines
