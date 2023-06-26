from hummingbot.data_feed.candles_feed.binance_perpetual_candles import BinancePerpetualCandles
from hummingbot.data_feed.candles_feed.binance_spot_candles import BinanceSpotCandles
from hummingbot.data_feed.candles_feed.gate_io_perpetual_candles import GateioPerpetualCandles
from hummingbot.data_feed.candles_feed.gate_io_spot_candles import GateioSpotCandles
from hummingbot.data_feed.candles_feed.kucoin_spot_candles.kucoin_spot_candles import KucoinSpotCandles


class CandlesFactory:
    """
    The CandlesFactory class creates and returns a Candle object based on the specified connector and trading pair.
    It has a class method, get_candle which takes in a connector, trading pair, interval, and max_records as parameters.
    Based on the connector provided, the method returns either a BinancePerpetualsCandles or a BinanceSpotCandles object.
    If an unsupported connector is provided, it raises an exception.
    """
    @classmethod
    def get_candle(cls, connector: str, trading_pair: str, interval: str = "1m", max_records: int = 500):
        if connector == "binance_perpetual":
            return BinancePerpetualCandles(trading_pair, interval, max_records)
        elif connector == "binance":
            return BinanceSpotCandles(trading_pair, interval, max_records)
        elif connector == "gate_io":
            return GateioSpotCandles(trading_pair, interval, max_records)
        elif connector == "gate_io_perpetual":
            return GateioPerpetualCandles(trading_pair, interval, max_records)
        elif connector == "kucoin":
            return KucoinSpotCandles(trading_pair, interval, max_records)
        else:
            raise Exception(f"The connector {connector} is not available. Please select another one.")
