from pydantic import BaseModel

from hummingbot.data_feed.candles_feed.ascend_ex_spot_candles.ascend_ex_spot_candles import AscendExSpotCandles
from hummingbot.data_feed.candles_feed.binance_perpetual_candles import BinancePerpetualCandles
from hummingbot.data_feed.candles_feed.binance_spot_candles import BinanceSpotCandles
from hummingbot.data_feed.candles_feed.gate_io_perpetual_candles import GateioPerpetualCandles
from hummingbot.data_feed.candles_feed.gate_io_spot_candles import GateioSpotCandles
from hummingbot.data_feed.candles_feed.kraken_spot_candles.kraken_spot_candles import KrakenSpotCandles
from hummingbot.data_feed.candles_feed.kucoin_spot_candles.kucoin_spot_candles import KucoinSpotCandles
from hummingbot.data_feed.candles_feed.okx_perpetual_candles.okx_perpetual_candles import OKXPerpetualCandles


class CandlesConfig(BaseModel):
    """
    The CandlesConfig class is a data class that stores the configuration of a Candle object.
    It has the following attributes:
    - connector: str
    - trading_pair: str
    - interval: str
    - max_records: int
    """
    connector: str
    trading_pair: str
    interval: str = "1m"
    max_records: int = 500


class CandlesFactory:
    """
    The CandlesFactory class creates and returns a Candle object based on the specified connector and trading pair.
    It has a class method, get_candle which takes in a connector, trading pair, interval, and max_records as parameters.
    Based on the connector provided, the method returns either a BinancePerpetualsCandles or a BinanceSpotCandles object.
    If an unsupported connector is provided, it raises an exception.
    """
    @classmethod
    def get_candle(cls, candles_config: CandlesConfig):
        """
        Returns a Candle object based on the specified connector and trading pair.
        :param candles_config: CandlesConfig
        :return: Candles
        """
        connector = candles_config.connector
        trading_pair = candles_config.trading_pair
        interval = candles_config.interval
        max_records = candles_config.max_records
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
        elif connector == "ascend_ex":
            return AscendExSpotCandles(trading_pair, interval, max_records)
        elif connector == "okx_perpetual":
            return OKXPerpetualCandles(trading_pair, interval, max_records)
        elif connector == "kraken":
            return KrakenSpotCandles(trading_pair, interval, max_records)
        else:
            raise Exception(f"The connector {connector} is not available. Please select another one.")
