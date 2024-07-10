from typing import Dict, Type

from hummingbot.data_feed.candles_feed.ascend_ex_spot_candles.ascend_ex_spot_candles import AscendExSpotCandles
from hummingbot.data_feed.candles_feed.binance_perpetual_candles import BinancePerpetualCandles
from hummingbot.data_feed.candles_feed.binance_spot_candles import BinanceSpotCandles
from hummingbot.data_feed.candles_feed.bybit_perpetual_candles.bybit_perpetual_candles import BybitPerpetualCandles
from hummingbot.data_feed.candles_feed.bybit_spot_candles.bybit_spot_candles import BybitSpotCandles
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.data_feed.candles_feed.gate_io_perpetual_candles import GateioPerpetualCandles
from hummingbot.data_feed.candles_feed.gate_io_spot_candles import GateioSpotCandles
from hummingbot.data_feed.candles_feed.hyperliquid_perpetual_candles.hyperliquid_perpetual_candles import (
    HyperliquidPerpetualCandles,
)
from hummingbot.data_feed.candles_feed.hyperliquid_spot_candles.hyperliquid_spot_candles import HyperliquidSpotCandles
from hummingbot.data_feed.candles_feed.kraken_spot_candles.kraken_spot_candles import KrakenSpotCandles
from hummingbot.data_feed.candles_feed.kucoin_perpetual_candles.kucoin_perpetual_candles import KucoinPerpetualCandles
from hummingbot.data_feed.candles_feed.kucoin_spot_candles.kucoin_spot_candles import KucoinSpotCandles
from hummingbot.data_feed.candles_feed.mexc_perpetual_candles.mexc_perpetual_candles import MexcPerpetualCandles
from hummingbot.data_feed.candles_feed.mexc_spot_candles.mexc_spot_candles import MexcSpotCandles
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
        "kucoin_perpetual": KucoinPerpetualCandles,
        "ascend_ex": AscendExSpotCandles,
        "okx_perpetual": OKXPerpetualCandles,
        "okx": OKXSpotCandles,
        "kraken": KrakenSpotCandles,
        "mexc": MexcSpotCandles,
        "mexc_perpetual": MexcPerpetualCandles,
        "bybit": BybitSpotCandles,
        "bybit_perpetual": BybitPerpetualCandles,
        "hyperliquid": HyperliquidSpotCandles,
        "hyperliquid_perpetual": HyperliquidPerpetualCandles
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
