"""
Simple factory for creating Gateway connectors.
"""
from typing import Optional

from ..core import GatewayConnector


class GatewayConnectorFactory:
    """
    Simple factory for creating Gateway connectors.
    """

    @staticmethod
    async def create(
        connector_name: str,
        network: str,
        wallet_address: Optional[str] = None,
        trading_required: bool = True
    ) -> GatewayConnector:
        """
        Create a Gateway connector instance.

        :param connector_name: Connector name (e.g., "raydium/amm")
        :param network: Network name (e.g., "mainnet-beta")
        :param wallet_address: Optional wallet address
        :param trading_required: Whether trading is required
        :return: GatewayConnector instance
        """
        # Create connector instance
        connector = GatewayConnector(
            connector_name=connector_name,
            network=network,
            wallet_address=wallet_address,
            trading_required=trading_required
        )

        # Wait for initialization
        await connector._initialize()

        return connector
