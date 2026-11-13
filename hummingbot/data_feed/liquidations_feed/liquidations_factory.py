from typing import Dict, Optional, Set, Type

from pydantic import BaseModel, SecretStr

from hummingbot.data_feed.liquidations_feed.agentfeed.agentfeed_liquidations import AgentFeedLiquidations
from hummingbot.data_feed.liquidations_feed.binance.binance_liquidations import BinancePerpetualLiquidations
from hummingbot.data_feed.liquidations_feed.liquidations_base import LiquidationsBase


class UnsupportedConnectorException(Exception):
    """
    Exception raised when an unsupported connector is requested.
    """

    def __init__(self, connector: str):
        message = f"The connector {connector} is not available. Please select another one."
        super().__init__(message)


class LiquidationsConfig(BaseModel):
    """
    A configuration class for LiquidationDataFeed.

    Attributes:
        connector (str): The identifier for the data source or exchange connector.
        trading_pairs (Set[str]): A set of trading pairs to subscribe to for liquidation events. If not provided,
                                  subscriptions will be made to all liquidations available on the exchange.
        max_retention_seconds (int): The maximum duration in seconds that liquidation data should be retained.
                                     Defaults to 60 seconds if not specified.
        api_key (SecretStr): For a source that needs a key (agentfeed). Falls back to the AGENTFEED_API_KEY environment
                             variable. Never logged.
        poll_interval_seconds (float): For a source that polls over REST (agentfeed). Defaults to 30 seconds, minimum 10.
    """
    connector: str
    trading_pairs: Optional[Set[str]] = None  # Optional, defaults to subscribing to all liquidations on that exchange
    max_retention_seconds: int = 60  # Default value set to 60 seconds
    api_key: Optional[SecretStr] = None
    poll_interval_seconds: Optional[float] = None


class LiquidationsFactory:
    """
    The LiquidationsFactory class creates and returns a liquidations data-feed object based on the specified
    configuration. It uses a mapping of connector names to their respective data-feed classes.
    """
    _liquidation_feeds_map: Dict[str, Type[LiquidationsBase]] = {
        "binance": BinancePerpetualLiquidations,
        "agentfeed": AgentFeedLiquidations,
    }

    @classmethod
    def get_liquidations_feed(cls, liquidations_config: LiquidationsConfig) -> LiquidationsBase:
        """
        Returns a Liquidation object based on the specified configuration.

        :param liquidations_config: LiquidationsConfig
        :return: Instance of LiquidationsBase or its subclass.
        :raises UnsupportedConnectorException: If the connector is not supported.
        """
        connector_class = cls._liquidation_feeds_map.get(liquidations_config.connector)
        if connector_class:
            extras = {}
            for field in connector_class.CONFIG_FIELDS:
                value = getattr(liquidations_config, field)
                if isinstance(value, SecretStr):
                    value = value.get_secret_value()
                extras[field] = value
            return connector_class(
                liquidations_config.trading_pairs,
                liquidations_config.max_retention_seconds,
                **extras
            )
        else:
            raise UnsupportedConnectorException(liquidations_config.connector)
