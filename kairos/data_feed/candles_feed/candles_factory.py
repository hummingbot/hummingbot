from typing import TYPE_CHECKING, Dict, Optional, Type

from kairos.data_feed.candles_feed.binance_perpetual_candles import BinancePerpetualCandles
from kairos.data_feed.candles_feed.binance_spot_candles import BinanceSpotCandles
from kairos.data_feed.candles_feed.candles_base import CandlesBase
from kairos.data_feed.candles_feed.data_types import CandlesConfig

if TYPE_CHECKING:
    from kairos.connector.connector_base import ConnectorBase


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
        "binance": BinanceSpotCandles,
        "binance_perpetual": BinancePerpetualCandles,
    }

    @classmethod
    def get_candle(cls, candles_config: CandlesConfig,
                   connector: Optional["ConnectorBase"] = None) -> CandlesBase:
        """
        Returns a Candle object based on the specified configuration.

        :param candles_config: CandlesConfig
        :param connector: Optional backing connector (same exchange). When provided, the feed shares
            the connector's rate-limit budget (its throttler) and reuses the connector's public
            symbol map and cached exchange-data instead of fetching them itself. When ``None`` the
            feed keeps its standalone behaviour (own throttler, own symbol/init-data logic).
        :return: Instance of CandleBase or its subclass.
        :raises UnsupportedConnectorException: If the connector is not supported.
        """
        connector_class = cls._candles_map.get(candles_config.connector)
        if connector_class:
            candle = connector_class(candles_config.trading_pair, candles_config.interval, candles_config.max_records)
            if connector is not None:
                candle.attach_connector(connector)
            return candle
        else:
            raise UnsupportedConnectorException(candles_config.connector)
