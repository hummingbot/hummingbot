from decimal import Decimal

from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig, CandlesFactory
from hummingbot.strategy.directional_strategy_base import DirectionalStrategyBase


class RSI(DirectionalStrategyBase):
    """
    相对强弱指数 (RSI) 策略实现基于 DirectionalStrategyBase。

    此策略使用 RSI 指标来生成交易信号并根据 RSI 值执行交易。
    它定义了 RSI 策略的特定参数和配置。

    参数：
        directional_strategy_name (str): 策略的名称。
        trading_pair (str): 要交易的交易对。
        exchange (str): 要用于交易的交易所。
        order_amount_usd (Decimal): 订单的美元金额。
        leverage (int): 要用于交易的杠杆。

    仓位参数：
        stop_loss (float): 该仓位的止损百分比。
        take_profit (float): 该仓位的获利了结百分比。
        time_limit (int): 该仓位的限时（秒）。
        trailing_stop_activation_delta (float): 跟随止损的激活增量。
        trailing_stop_trailing_delta (float): 跟随止损的跟随增量。

    蜡烛图配置：
        candles (List[CandlesBase]): 用于生成信号的蜡烛图列表。

    市场：
        指定策略的市场和交易对的字典。

    方法：
        get_signal(): 根据 RSI 指标生成交易信号。
        get_processed_df(): 检索具有 RSI 值的已处理数据帧。
        market_data_extra_info(): 提供有关市场数据的其他信息。

    继承自：
        DirectionalStrategyBase：使用 PositionExecutor 创建方向策略的基类。
    """

    directional_strategy_name: str = "RSI"
    # Define the trading pair and exchange that we want to use and the csv where we are going to store the entries
    trading_pair: str = "ETH-USDT"
    exchange: str = "binance_perpetual"
    order_amount_usd = Decimal("40")
    leverage = 10

    # Configure the parameters for the position
    stop_loss: float = 0.0075
    take_profit: float = 0.015
    time_limit: int = 60 * 1
    trailing_stop_activation_delta = 0.004
    trailing_stop_trailing_delta = 0.001
    cooldown_after_execution = 10

    candles = [
        CandlesFactory.get_candle(
            CandlesConfig(connector=exchange, trading_pair=trading_pair, interval="3m", max_records=1000)
        )
    ]
    markets = {exchange: {trading_pair}}

    def get_signal(self):
        """
        Generates the trading signal based on the RSI indicator.
        Returns:
            int: The trading signal (-1 for sell, 0 for hold, 1 for buy).
        """
        candles_df = self.get_processed_df()
        rsi_value = candles_df.iat[-1, -1]
        if rsi_value > 70:
            return -1
        elif rsi_value < 30:
            return 1
        else:
            return 0

    def get_processed_df(self):
        """
        Retrieves the processed dataframe with RSI values.
        Returns:
            pd.DataFrame: The processed dataframe with RSI values.
        """
        candles_df = self.candles[0].candles_df
        candles_df.ta.rsi(length=7, append=True)
        return candles_df

    def market_data_extra_info(self):
        """
        Provides additional information about the market data to the format status.
        Returns:
            List[str]: A list of formatted strings containing market data information.
        """
        lines = []
        columns_to_show = ["timestamp", "open", "low", "high", "close", "volume", "RSI_7"]
        candles_df = self.get_processed_df()
        lines.extend([f"Candles: {self.candles[0].name} | Interval: {self.candles[0].interval}\n"])
        lines.extend(self.candles_formatted_list(candles_df, columns_to_show))
        return lines
