from hummingbot.data_feed.candles_feed.binance_perpetuals_candles import BinancePerpetualsCandles
from hummingbot.data_feed.candles_feed.binance_spot_candles import BinanceSpotCandles


class CandlesFactory:

    @classmethod
    def get_candle(cls, connector: str, trading_pair: str, interval: str = "1m", max_records: int = 500):
        if connector == "binance_perpetuals":
            return BinancePerpetualsCandles(trading_pair, interval, max_records)
        elif connector == "binance_spot":
            return BinanceSpotCandles(trading_pair, interval, max_records)
        else:
            raise Exception(f"The connector {connector} is not available. Please select another one.")
