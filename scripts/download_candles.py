from typing import Dict

from hummingbot import data_path
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DownloadCandles(ScriptStrategyBase):
    """
    This script provides an example of how to use the Candles Feed to download and store historical data.
    It downloads 3-minute candles for 3 Binance trading pairs ["APE-USDT", "BTC-USDT", "BNB-USDT"] and stores them in
    CSV files in the /data directory. The script stops after it has downloaded 50,000 max_records records for each pair.
    Is important to notice that the component will fail if all the candles are not available since the idea of it is to
    use it in production based on candles needed to compute technical indicators.
    """
    trading_pairs = ["APE-USDT", "BTC-USDT", "BNB-USDT"]
    intervals = ["3m", "1m", "5m"]
    max_records = 50000
    # we can initialize any trading pair since we only need the candles
    markets = {"binance_paper_trade": {"BTC-USDT"}}

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        combinations = [(trading_pair, interval) for trading_pair in self.trading_pairs for interval in self.intervals]

        self.candles = {f"{combinations[0]}_{combinations[1]}": {} for combinations in combinations}
        # we need to initialize the candles for each trading pair
        for combination in combinations:
            candle = CandlesFactory.get_candle(connector="binance", trading_pair=combination[0],
                                               interval=combination[1],
                                               max_records=self.max_records)
            candle.start()
            # we are storing the candles object and the csv path to save the candles
            self.candles[f"{combination[0]}_{combination[1]}"]["candles"] = candle
            self.candles[f"{combination[0]}_{combination[1]}"][
                "csv_path"] = data_path() + f"/candles_{combination[0]}_{combination[1]}.csv"

    def on_tick(self):
        for trading_pair, candles_info in self.candles.items():
            if not candles_info["candles"].is_ready:
                self.logger().info(f"Candles not ready yet for {trading_pair}! Missing {candles_info['candles']._candles.maxlen - len(candles_info['candles']._candles)}")
                pass
            else:
                df = candles_info["candles"].candles_df
                df.to_csv(candles_info["csv_path"], index=False)
        if all(candles_info["candles"].is_ready for candles_info in self.candles.values()):
            HummingbotApplication.main_application().stop()

    def on_stop(self):
        for candles_info in self.candles.values():
            candles_info["candles"].stop()
