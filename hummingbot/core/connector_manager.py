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
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.model.sql_connection_manager import SQLConnectionManager


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

        # Trade fill database for potential future use
        self._trade_fill_db: Optional[SQLConnectionManager] = None

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
                if not keys:
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

            self._logger.info(f"Created connector: {connector_name} with pairs: {trading_pairs}")

            return connector

        except Exception as e:
            self._logger.error(f"Failed to create connector {connector_name}: {e}")
            raise

    async def remove_connector(self, connector_name: str) -> bool:
        """
        Remove a connector and clean up resources.

        Args:
            connector_name: Name of the connector to remove

        Returns:
            bool: True if successfully removed
        """
        try:
            if connector_name not in self.connectors:
                self._logger.warning(f"Connector {connector_name} not found")
                return False

            connector = self.connectors[connector_name]

            # Cancel all orders before removing
            if len(connector.limit_orders) > 0:
                self._logger.info(f"Canceling orders on {connector_name}...")
                await connector.cancel_all(10.0)

            # Stop the connector
            connector.stop()

            # Remove from active connectors
            del self.connectors[connector_name]

            self._logger.info(f"Removed connector: {connector_name}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to remove connector {connector_name}: {e}")
            return False

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
        await self.remove_connector(connector_name)
        self.create_connector(connector_name, all_pairs)

        return True

    def get_connector(self, connector_name: str) -> Optional[ExchangeBase]:
        """Get a connector by name."""
        return self.connectors.get(connector_name)

    def get_all_connectors(self) -> Dict[str, ExchangeBase]:
        """Get all active connectors."""
        return self.connectors.copy()

    async def place_order(self,
                          connector_name: str,
                          trading_pair: str,
                          order_type: OrderType,
                          trade_type: TradeType,
                          amount: float,
                          price: Optional[float] = None) -> str:
        """
        Place an order directly through a connector.

        Args:
            connector_name: Name of the connector
            trading_pair: Trading pair
            order_type: LIMIT or MARKET
            trade_type: BUY or SELL
            amount: Order amount
            price: Order price (required for LIMIT orders)

        Returns:
            str: Order ID
        """
        connector = self.get_connector(connector_name)
        if not connector:
            raise ValueError(f"Connector {connector_name} not found")

        if order_type == OrderType.LIMIT:
            if price is None:
                raise ValueError("Price required for LIMIT orders")
            if trade_type == TradeType.BUY:
                order_id = connector.buy(trading_pair, amount, order_type, price)
            else:
                order_id = connector.sell(trading_pair, amount, order_type, price)
        else:  # MARKET order
            if trade_type == TradeType.BUY:
                order_id = connector.buy(trading_pair, amount, order_type)
            else:
                order_id = connector.sell(trading_pair, amount, order_type)

        self._logger.info(f"Placed {trade_type.name} {order_type.name} order {order_id} on {connector_name}")
        return order_id

    async def cancel_order(self, connector_name: str, trading_pair: str, order_id: str) -> bool:
        """Cancel an order."""
        connector = self.get_connector(connector_name)
        if not connector:
            return False

        return await connector.cancel(trading_pair, order_id)

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
