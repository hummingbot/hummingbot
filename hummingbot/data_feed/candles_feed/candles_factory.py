from typing import Dict, Type

from hummingbot.data_feed.candles_feed.ascend_ex_spot_candles.ascend_ex_spot_candles import AscendExSpotCandles
from hummingbot.data_feed.candles_feed.binance_perpetual_candles import BinancePerpetualCandles
from hummingbot.data_feed.candles_feed.binance_spot_candles import BinanceSpotCandles
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.data_feed.candles_feed.gate_io_perpetual_candles import GateioPerpetualCandles
from hummingbot.data_feed.candles_feed.gate_io_spot_candles import GateioSpotCandles
from hummingbot.data_feed.candles_feed.kraken_spot_candles.kraken_spot_candles import KrakenSpotCandles
from hummingbot.data_feed.candles_feed.kucoin_spot_candles.kucoin_spot_candles import KucoinSpotCandles
from hummingbot.data_feed.candles_feed.okx_perpetual_candles.okx_perpetual_candles import OKXPerpetualCandles
from hummingbot.data_feed.candles_feed.okx_spot_candles.okx_spot_candles import OKXSpotCandles


class UnsupportedConnectorException(Exception):
    """
    Exception raised when an unsupported connector is requested.
    """
    def __init__(self, connector: str):
        message = f"The connector {connector} is not available. Please select another one."
        super().__init__(message)


class CandlesFactory:
    """
    The CandlesFactory class creates and returns a Candle object based on the specified configuration.
    It uses a mapping of connector names to their respective candle classes.
    """
    _candles_map: Dict[str, Type[CandlesBase]] = {
        "binance_perpetual": BinancePerpetualCandles,
        "binance": BinanceSpotCandles,
        "gate_io": GateioSpotCandles,
        "gate_io_perpetual": GateioPerpetualCandles,
        "kucoin": KucoinSpotCandles,
        "ascend_ex": AscendExSpotCandles,
        "okx_perpetual": OKXPerpetualCandles,
        "okx": OKXSpotCandles,
        "kraken": KrakenSpotCandles
    }

    @classmethod
    def get_candle(cls, candles_config: CandlesConfig) -> CandlesBase:
        """
        Returns a Candle object based on the specified configuration.

        :param candles_config: CandlesConfig
        :return: Instance of CandleBase or its subclass.
        :raises UnsupportedConnectorException: If the connector is not supported.
        """
        connector_class = cls._candles_map.get(candles_config.connector)
        if connector_class:
            return connector_class(
                candles_config.trading_pair,
                candles_config.interval,
                candles_config.max_records
            )
        else:
            raise UnsupportedConnectorException(candles_config.connector)
