"""
Gateway Connector Factory

This module provides a factory function to create the appropriate gateway connector
based on connector name and trading type, validating against Gateway's available connectors.
"""
from typing import Any, Dict, Optional, Type

from hummingbot.connector.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.connector.gateway.gateway_lp import GatewayLp
from hummingbot.connector.gateway.gateway_swap import GatewaySwap
from hummingbot.logger import HummingbotLogger


class GatewayConnectorFactory:
    """Factory class for creating gateway connectors based on trading type."""

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            from hummingbot.logger import HummingbotLogger
            cls._logger = HummingbotLogger(__name__)
        return cls._logger

    # Mapping of trading types to connector classes
    TRADING_TYPE_TO_CLASS: Dict[str, Type] = {
        "swap": GatewaySwap,
        "amm": GatewayLp,  # AMM uses GatewayLp
        "clmm": GatewayLp,  # CLMM uses GatewayLp
        "lp": GatewayLp,
    }

    @classmethod
    async def get_connector_class(
        cls,
        connector_name: str,
        trading_type: Optional[str],
        chain: str,
        network: str,
        validate: bool = True
    ) -> Optional[Type]:
        """
        Get the appropriate connector class for the given connector and trading type.

        Args:
            connector_name: Name of the connector (e.g., "uniswap", "jupiter", "raydium")
            trading_type: Trading type (e.g., "swap", "amm", "clmm") or None to use first available
            chain: Blockchain chain (e.g., "ethereum", "solana")
            network: Network name (e.g., "mainnet", "mainnet-beta")
            validate: Whether to validate against Gateway's available connectors

        Returns:
            The appropriate connector class, or None if validation fails

        Raises:
            ValueError: If connector or trading type is not supported
        """
        supported_types = []

        if validate or trading_type is None:
            # Get available connectors from Gateway
            gateway_client = GatewayHttpClient.get_instance()
            try:
                connectors_response = await gateway_client.get_connectors()
                connectors = connectors_response.get("connectors", [])

                # Find the matching connector
                matching_connector = None
                for conn in connectors:
                    if conn.get("name", "").lower() == connector_name.lower():
                        matching_connector = conn
                        break

                if not matching_connector:
                    raise ValueError(f"Connector '{connector_name}' not found in Gateway")

                # Get supported trading types
                supported_types = matching_connector.get("trading_types", [])

                # If no trading type specified, use the first available
                if trading_type is None:
                    if not supported_types:
                        raise ValueError(f"Connector '{connector_name}' has no trading types defined")
                    trading_type = supported_types[0].lower()
                    cls.logger().info(
                        f"No trading type specified for '{connector_name}', using first available: '{trading_type}'"
                    )
                else:
                    # Validate the requested trading type
                    trading_type = trading_type.lower()
                    if trading_type not in [t.lower() for t in supported_types]:
                        raise ValueError(
                            f"Connector '{connector_name}' does not support trading type '{trading_type}'. "
                            f"Supported types: {', '.join(supported_types)}"
                        )

                # Log the connector info for debugging
                cls.logger().info(
                    f"Validated connector '{connector_name}' with trading types: {supported_types}"
                )

            except Exception as e:
                cls.logger().error(f"Failed to validate connector: {str(e)}")
                if validate:
                    raise
        else:
            # If not validating and trading_type is provided, normalize it
            trading_type = trading_type.lower()

        # Determine the appropriate class based on trading type
        if trading_type in cls.TRADING_TYPE_TO_CLASS:
            connector_class = cls.TRADING_TYPE_TO_CLASS[trading_type]
        else:
            # For AMM/CLMM types, use the LP connector as fallback
            if trading_type in ["amm", "clmm"]:
                connector_class = GatewayLp
            else:
                raise ValueError(f"Unsupported trading type: {trading_type}")

        cls.logger().info(
            f"Selected {connector_class.__name__} for {connector_name}/{trading_type}"
        )

        return connector_class

    @classmethod
    async def create_connector(
        cls,
        connector_name: str,
        trading_type: Optional[str],
        chain: str,
        network: str,
        wallet_address: str,
        trading_pairs: list = None,
        trading_required: bool = False,
        client_config_map: Any = None,
        **kwargs
    ) -> Any:
        """
        Create a gateway connector instance with the appropriate class.

        Args:
            connector_name: Name of the connector
            trading_type: Trading type or None to use first available
            chain: Blockchain chain
            network: Network name
            wallet_address: Wallet address to use
            trading_pairs: List of trading pairs
            trading_required: Whether trading is required
            client_config_map: Client configuration
            **kwargs: Additional connector-specific parameters

        Returns:
            Configured connector instance
        """
        # Get the appropriate connector class
        connector_class = await cls.get_connector_class(
            connector_name, trading_type, chain, network, validate=True
        )

        if not connector_class:
            raise ValueError(
                f"Could not determine connector class for {connector_name}/{trading_type}"
            )

        # Prepare initialization parameters
        init_params = {
            "connector_name": connector_name,
            "chain": chain,
            "network": network,
            "address": wallet_address,
            "trading_pairs": trading_pairs or [],
            "trading_required": trading_required,
            "client_config_map": client_config_map,
        }

        # Add any additional parameters
        init_params.update(kwargs)

        # Create and return the connector instance
        connector = connector_class(**init_params)

        cls.logger().info(
            f"Created {connector_class.__name__} instance for {connector_name} "
            f"on {chain}/{network} with wallet {wallet_address}"
        )

        return connector


# Convenience function for direct usage
async def get_gateway_connector_class(
    connector_name: str,
    trading_type: Optional[str] = None,
    chain: str = None,
    network: str = None,
    validate: bool = True
) -> Optional[Type]:
    """
    Convenience function to get the appropriate gateway connector class.

    See GatewayConnectorFactory.get_connector_class for parameters.
    """
    return await GatewayConnectorFactory.get_connector_class(
        connector_name, trading_type, chain, network, validate
    )
