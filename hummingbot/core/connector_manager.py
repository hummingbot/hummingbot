import logging
from typing import Any, Dict, List, Optional

from hummingbot.client.config.config_helpers import (
    ClientConfigAdapter,
    ReadOnlyClientConfigAdapter,
    get_connector_class,
)
from hummingbot.client.config.security import Security
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.connector.exchange.paper_trade import create_paper_trade_market
from hummingbot.connector.exchange_base import ExchangeBase


class ConnectorManager:
    """
    Manages connectors (exchanges) dynamically.

    This class provides functionality to:
    - Create and initialize connectors on the fly
    - Add/remove connectors dynamically
    - Access market data without strategies
    - Place orders directly through connectors
    - Manage connector lifecycle independently of strategies
    """

    def __init__(self, client_config: ClientConfigAdapter):
        """
        Initialize the connector manager.

        Args:
            client_config: Client configuration
        """
        self._logger = logging.getLogger(__name__)
        self.client_config_map = client_config

        # Active connectors
        self.connectors: Dict[str, ExchangeBase] = {}

    def create_connector(self,
                         connector_name: str,
                         trading_pairs: List[str],
                         trading_required: bool = True,
                         api_keys: Optional[Dict[str, str]] = None) -> ExchangeBase:
        """
        Create and initialize a connector.

        Args:
            connector_name: Name of the connector (e.g., 'binance', 'kucoin')
            trading_pairs: List of trading pairs to support
            trading_required: Whether this connector will be used for trading
            api_keys: Optional API keys dict

        Returns:
            ExchangeBase: Initialized connector instance
        """
        try:
            # Check if connector already exists
            if connector_name in self.connectors:
                self._logger.warning(f"Connector {connector_name} already exists")
                return self.connectors[connector_name]

            # Handle paper trading connector names
            if connector_name.endswith("_paper_trade"):
                base_connector_name = connector_name.replace("_paper_trade", "")
                conn_setting = AllConnectorSettings.get_connector_settings()[base_connector_name]
            else:
                base_connector_name = connector_name
                conn_setting = AllConnectorSettings.get_connector_settings()[connector_name]

            # Handle paper trading
            if connector_name.endswith("paper_trade"):

                base_connector = base_connector_name
                connector = create_paper_trade_market(
                    base_connector,
                    self.client_config_map,
                    trading_pairs
                )

                # Set paper trade balances if configured
                paper_trade_account_balance = self.client_config_map.paper_trade.paper_trade_account_balance
                if paper_trade_account_balance is not None:
                    for asset, balance in paper_trade_account_balance.items():
                        connector.set_balance(asset, balance)
            else:
                # Create live connector
                keys = api_keys or Security.api_keys(connector_name)
                if not keys and not conn_setting.uses_gateway_generic_connector():
                    raise ValueError(f"API keys required for live trading connector '{connector_name}'. "
                                     f"Either provide API keys or use a paper trade connector.")
                read_only_config = ReadOnlyClientConfigAdapter.lock_config(self.client_config_map)

                init_params = conn_setting.conn_init_parameters(
                    trading_pairs=trading_pairs,
                    trading_required=trading_required,
                    api_keys=keys,
                    client_config_map=read_only_config,
                )

                connector_class = get_connector_class(connector_name)
                connector = connector_class(**init_params)

            # Add to active connectors
            self.connectors[connector_name] = connector

            self._logger.info(f"Created connector: {connector_name}")

            return connector

        except Exception as e:
            self._logger.error(f"Failed to create connector {connector_name}: {e}")
            raise

    def remove_connector(self, connector_name: str) -> bool:
        """
        Remove a connector and clean up resources.

        Args:
            connector_name: Name of the connector to remove

        Returns:
            bool: True if successfully removed
        """
        if connector_name not in self.connectors:
            self._logger.warning(f"Connector {connector_name} not found")
            return False

        del self.connectors[connector_name]
        self._logger.info(f"Removed connector: {connector_name}")
        return True

    async def add_trading_pairs(self, connector_name: str, trading_pairs: List[str]) -> bool:
        """
        Add trading pairs to an existing connector.

        Args:
            connector_name: Name of the connector
            trading_pairs: List of trading pairs to add

        Returns:
            bool: True if successfully added
        """
        if connector_name not in self.connectors:
            self._logger.error(f"Connector {connector_name} not found")
            return False

        # Most connectors require recreation to add pairs
        # So we'll recreate with the combined list
        connector = self.connectors[connector_name]
        existing_pairs = connector.trading_pairs
        all_pairs = list(set(existing_pairs + trading_pairs))

        # Remove and recreate
        self.remove_connector(connector_name)
        self.create_connector(connector_name, all_pairs)

        return True

    @staticmethod
    def is_gateway_market(connector_name: str) -> bool:
        return connector_name in AllConnectorSettings.get_gateway_amm_connector_names()

    def get_connector(self, connector_name: str) -> Optional[ExchangeBase]:
        """Get a connector by name."""
        return self.connectors.get(connector_name)

    def get_all_connectors(self) -> Dict[str, ExchangeBase]:
        """Get all active connectors."""
        return self.connectors.copy()

    def get_order_book(self, connector_name: str, trading_pair: str) -> Any:
        """Get order book for a trading pair."""
        connector = self.get_connector(connector_name)
        if not connector:
            return None

        return connector.get_order_book(trading_pair)

    def get_balance(self, connector_name: str, asset: str) -> float:
        """Get balance for an asset."""
        connector = self.get_connector(connector_name)
        if not connector:
            return 0.0

        return connector.get_balance(asset)

    def get_all_balances(self, connector_name: str) -> Dict[str, float]:
        """Get all balances from a connector."""
        connector = self.get_connector(connector_name)
        if not connector:
            return {}

        return connector.get_all_balances()

    async def update_connector_balances(self, connector_name: str):
        """
        Update balances for a specific connector.

        Args:
            connector_name: Name of the connector to update balances for
        """
        connector = self.get_connector(connector_name)
        if connector:
            await connector._update_balances()
        else:
            raise ValueError(f"Connector {connector_name} not found")

    def get_status(self) -> Dict[str, Any]:
        """Get status of all connectors."""
        status = {}
        for name, connector in self.connectors.items():
            status[name] = {
                'ready': connector.ready,
                'trading_pairs': connector.trading_pairs,
                'orders_count': len(connector.limit_orders),
                'balances': connector.get_all_balances() if connector.ready else {}
            }
        return status
