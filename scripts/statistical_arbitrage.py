from decimal import Decimal

from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.strategy.directional_strategy_base import DirectionalStrategyBase


class StatisticalArbitrage(DirectionalStrategyBase):
    directional_strategy_name: str = "statistical_arbitrage"
    # Define the trading pair and exchange that we want to use and the csv where we are going to store the entries
    trading_pair: str = "ETH-USDT"
    trading_pair_2: str = "BTC-USDT"
    exchange: str = "binance_perpetual"
    order_amount_usd = Decimal("15")
    leverage = 10

    # Configure the parameters for the position
    stop_loss: float = 0.0075
    take_profit: float = 0.015
    time_limit: int = None
    trailing_stop_activation_delta = 0.004
    trailing_stop_trailing_delta = 0.001

    candles = [
        CandlesFactory.get_candle(connector=exchange,
                                  trading_pair=trading_pair,
                                  interval="1m", max_records=150),
        CandlesFactory.get_candle(connector=exchange,
                                  trading_pair=trading_pair_2,
                                  interval="1m", max_records=150),
    ]
    markets = {exchange: {trading_pair}}

    def get_signal(self):

        signals = []
        for candle in self.candles:
            candles_df = self.get_processed_df(candle.candles_df)
            last_row = candles_df.iloc[-1]

            signal_value = last_row["ZS_21"].item()

            signals.append(signal_value)

        if signals[0] > 2:
            return 1
        elif signals[0] < -2:
            return -1
        else:
            return 0

    @staticmethod
    def get_processed_df(candles):

        candles_df = candles.copy()
        # calc z-score
        # model = sm.OLS(candles[0], candles[1]).fit()
        # hedge_ratio = model.params[0]
        # spread = pd.Series(candles[0]) - (pd.Series(candles[1]) * hedge_ratio)
        # spread_df = pd.DataFrame(spread)
        # candles_df.ta.zscore(spread_df, length=21, append=True)
        candles_df.ta.zscore(length=21, append=True)

        return candles_df

    def market_data_extra_info(self):
        """
        Provides additional information about the market data for each candlestick.
        Returns:
            List[str]: A list of formatted strings containing market data information.
        """
        lines = []
        columns_to_show = ["timestamp", "open", "low", "high", "close", "volume", "ZS_21"]
        for candle in self.candles:
            candles_df = self.get_processed_df(candle.candles_df)
            lines.extend([f"Candles: {candle.name} | Interval: {candle.interval}\n"])
            lines.extend(self.candles_formatted_list(candles_df, columns_to_show))
        return lines
