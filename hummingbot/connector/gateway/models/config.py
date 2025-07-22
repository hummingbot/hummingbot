"""
Configuration models for Gateway connectors.
"""
from dataclasses import dataclass, field
from typing import List, Optional

from .types import TradingType


@dataclass
class ConnectorConfig:
    """
    Simplified configuration for a Gateway connector.
    All dynamic config parameters are fetched from Gateway as needed.
    """
    name: str
    chain: str
    network: str
    trading_types: List[TradingType] = field(default_factory=list)
    wallet_address: Optional[str] = None

    @classmethod
    async def from_gateway(
        cls,
        client,
        connector_name: str,
        network: str,
        wallet_address: Optional[str] = None
    ) -> "ConnectorConfig":
        """
        Load configuration from Gateway API.

        :param client: GatewayHttpClient instance
        :param connector_name: Connector name (e.g., "raydium/amm")
        :param network: Network name (e.g., "mainnet-beta")
        :param wallet_address: Optional wallet address
        :return: ConnectorConfig instance
        """
        # Get connector info to determine chain
        connector_info = await client.get_connector_info(connector_name)
        if not connector_info:
            raise ValueError(f"Connector {connector_name} not found")

        # Get chain from connector info
        chain = connector_info.get("chain", "").lower()
        if not chain:
            raise ValueError(f"Connector {connector_name} does not specify a chain")

        # Get trading types
        trading_types = []
        for tt in connector_info.get("trading_types", []):
            try:
                trading_types.append(TradingType(tt))
            except ValueError:
                # Skip unknown trading types
                pass

        # Get wallet address if not provided
        if not wallet_address:
            # Get default wallet for the chain
            wallet_address = await client.get_default_wallet_for_chain(chain)

            if not wallet_address:
                raise ValueError(f"No default wallet configured for {chain}. Please set a default wallet using 'gateway wallet setDefault'.")

        return cls(
            name=connector_name,
            chain=chain,
            network=network,
            trading_types=trading_types,
            wallet_address=wallet_address
        )
