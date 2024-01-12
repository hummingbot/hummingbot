import pandas as pd
import pandas_ta as ta  # noqa: F401

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.connector.connector_base import ConnectorBase, Dict
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig, CandlesFactory
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class VolatilityScreener(ScriptStrategyBase):
    exchange = "binance_perpetual"
    trading_pairs = ["BTC-USDT", "ETH-USDT", "BNB-USDT", "NEO-USDT", "INJ-USDT", "API3-USDT", "TRB-USDT",
                     "LPT-USDT", "SOL-USDT", "LTC-USDT", "DOT-USDT", "LINK-USDT", "UNI-USDT", "AAVE-USDT"]
    intervals = ["1h"]
    max_records = 500

    volatility_interval = 200
    columns_to_show = ["trading_pair", "bbands_width_pct", "bbands_percentage"]
    sort_values_by = ["bbands_percentage", "bbands_width_pct"]
    top_n = 10
    report_interval = 60 * 60 * 6  # 6 hours

    # we can initialize any trading pair since we only need the candles
    markets = {"binance_paper_trade": {"BTC-USDT"}}

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.last_time_reported = 0
        combinations = [(trading_pair, interval) for trading_pair in self.trading_pairs for interval in
                        self.intervals]

        self.candles = {f"{combinations[0]}_{combinations[1]}": None for combinations in combinations}
        # we need to initialize the candles for each trading pair
        for combination in combinations:
            candle = CandlesFactory.get_candle(
                CandlesConfig(connector=self.exchange, trading_pair=combination[0], interval=combination[1],
                              max_records=self.max_records))
            candle.start()
            self.candles[f"{combination[0]}_{combination[1]}"] = candle

    def on_tick(self):
        for trading_pair, candles in self.candles.items():
            if not candles.is_ready:
                self.logger().info(
                    f"Candles not ready yet for {trading_pair}! Missing {candles._candles.maxlen - len(candles._candles)}")
        if all(candle.is_ready for candle in self.candles.values()):
            if self.current_timestamp - self.last_time_reported > self.report_interval:
                self.last_time_reported = self.current_timestamp
                self.notify_hb_app(self.get_formatted_market_analysis())

    def on_stop(self):
        for candle in self.candles.values():
            candle.stop()

    def get_formatted_market_analysis(self):
        volatility_metrics_df = self.get_market_analysis()
        volatility_metrics_pct_str = format_df_for_printout(
            volatility_metrics_df[self.columns_to_show].sort_values(by=self.sort_values_by).head(self.top_n),
            table_format="psql")
        return volatility_metrics_pct_str

    def format_status(self) -> str:
        if all(candle.is_ready for candle in self.candles.values()):
            lines = []
            lines.extend(["Configuration:", f"Volatility Interval: {self.volatility_interval}"])
            lines.extend(["", "Volatility Metrics", ""])
            lines.extend([self.get_formatted_market_analysis()])
            return "\n".join(lines)
        else:
            return "Candles not ready yet!"

    def get_market_analysis(self):
        market_metrics = {}
        for trading_pair_interval, candle in self.candles.items():
            df = candle.candles_df
            df["trading_pair"] = trading_pair_interval.split("_")[0]
            df["interval"] = trading_pair_interval.split("_")[1]
            # adding volatility metrics
            df["volatility"] = df["close"].pct_change().rolling(self.volatility_interval).std()
            df["volatility_pct"] = df["volatility"] / df["close"]
            df["volatility_pct_mean"] = df["volatility_pct"].rolling(self.volatility_interval).mean()

            # adding bbands metrics
            df.ta.bbands(length=self.volatility_interval, append=True)
            df["bbands_width_pct"] = df[f"BBB_{self.volatility_interval}_2.0"]
            df["bbands_width_pct_mean"] = df["bbands_width_pct"].rolling(self.volatility_interval).mean()
            df["bbands_percentage"] = df[f"BBP_{self.volatility_interval}_2.0"]
            market_metrics[trading_pair_interval] = df.iloc[-1]
        volatility_metrics_df = pd.DataFrame(market_metrics).T
        return volatility_metrics_df
