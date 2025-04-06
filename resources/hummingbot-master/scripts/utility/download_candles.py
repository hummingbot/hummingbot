import os
from typing import Dict

from hummingbot import data_path
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DownloadCandles(ScriptStrategyBase):
    """
    This script provides an example of how to use the Candles Feed to download and store historical data.
    It downloads 3-minute candles for 3 Binance trading pairs ["APE-USDT", "BTC-USDT", "BNB-USDT"] and stores them in
    CSV files in the /data directory. The script stops after it has downloaded 50,000 max_records records for each pair.
    Is important to notice that the component will fail if all the candles are not available since the idea of it is to
    use it in production based on candles needed to compute technical indicators.
    """
    exchange = os.getenv("EXCHANGE", "binance")
    trading_pairs = os.getenv("TRADING_PAIRS", "BTC-USDT,ETH-USDT").split(",")
    intervals = os.getenv("INTERVALS", "1m,3m,5m,1h").split(",")
    days_to_download = int(os.getenv("DAYS_TO_DOWNLOAD", "3"))
    # we can initialize any trading pair since we only need the candles
    markets = {"kucoin_paper_trade": {"BTC-USDT"}}

    @staticmethod
    def get_max_records(days_to_download: int, interval: str) -> int:
        conversion = {"s": 1 / 60, "m": 1, "h": 60, "d": 1440}
        unit = interval[-1]
        quantity = int(interval[:-1])
        return int(days_to_download * 24 * 60 / (quantity * conversion[unit]))

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        combinations = [(trading_pair, interval) for trading_pair in self.trading_pairs for interval in self.intervals]

        self.candles = {f"{combinations[0]}_{combinations[1]}": {} for combinations in combinations}
        # we need to initialize the candles for each trading pair
        for combination in combinations:

            candle = CandlesFactory.get_candle(CandlesConfig(connector=self.exchange, trading_pair=combination[0], interval=combination[1], max_records=self.get_max_records(self.days_to_download, combination[1])))
            candle.start()
            # we are storing the candles object and the csv path to save the candles
            self.candles[f"{combination[0]}_{combination[1]}"]["candles"] = candle
            self.candles[f"{combination[0]}_{combination[1]}"][
                "csv_path"] = data_path() + f"/candles_{self.exchange}_{combination[0]}_{combination[1]}.csv"

    def on_tick(self):
        for trading_pair, candles_info in self.candles.items():
            if not candles_info["candles"].ready:
                self.logger().info(f"Candles not ready yet for {trading_pair}! Missing {candles_info['candles']._candles.maxlen - len(candles_info['candles']._candles)}")
                pass
            else:
                df = candles_info["candles"].candles_df
                df.to_csv(candles_info["csv_path"], index=False)
        if all(candles_info["candles"].ready for candles_info in self.candles.values()):
            HummingbotApplication.main_application().stop()

    async def on_stop(self):
        for candles_info in self.candles.values():
            candles_info["candles"].stop()
