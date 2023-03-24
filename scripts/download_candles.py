from hummingbot import data_path
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DownloadCandles(ScriptStrategyBase):
    trading_pair = "APE-USDT"
    interval = "3m"
    candles = CandlesFactory.get_candle(connector="binance", trading_pair=trading_pair, interval=interval, max_records=175000)
    candles.start()

    csv_path = data_path() + f"/candles_{trading_pair}_{interval}.csv"
    markets = {"binance_paper_trade": {"BTC-USDT"}}

    def on_tick(self):
        if not self.candles.is_ready:
            self.logger().info(f"Candles not ready yet! Missing {self.candles._candles.maxlen - len(self.candles._candles)}")
            pass
        else:
            df = self.candles.candles_df
            df.to_csv(self.csv_path, index=False)
            HummingbotApplication.main_application().stop()

    def on_stop(self):
        self.candles.stop()
