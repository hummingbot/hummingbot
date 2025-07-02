"""
Configuration models for Gateway connectors.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from .types import TradingType


@dataclass
class BaseNetworkConfig:
    """Base network configuration with common fields."""
    chain: str
    network: str
    node_url: str
    native_currency_symbol: str
    default_compute_units: int = 200000
    gas_estimate_interval: int = 60
    max_fee: float = 0.01
    min_fee: float = 0.0001
    retry_count: int = 3
    retry_fee_multiplier: float = 2.0
    retry_interval: int = 2


@dataclass
class EthereumNetworkConfig(BaseNetworkConfig):
    """Ethereum-specific network configuration."""
    chain_id: int = 1
    gas_price_refresh_interval: int = 60
    gas_limit_transaction: int = 3000000
    manual_gas_price: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any], network: str) -> "EthereumNetworkConfig":
        """Create EthereumNetworkConfig from dictionary."""
        return cls(
            chain="ethereum",
            network=network,
            node_url=data.get("nodeURL", ""),
            native_currency_symbol=data.get("nativeCurrencySymbol", "ETH"),
            chain_id=data.get("chainID", 1),
            default_compute_units=data.get("defaultComputeUnits", 200000),
            gas_estimate_interval=data.get("gasEstimateInterval", 60),
            max_fee=data.get("maxFee", 0.01),
            min_fee=data.get("minFee", 0.0001),
            retry_count=data.get("retryCount", 3),
            retry_fee_multiplier=data.get("retryFeeMultiplier", 2.0),
            retry_interval=data.get("retryInterval", 2),
            gas_price_refresh_interval=data.get("gasPriceRefreshInterval", 60),
            gas_limit_transaction=data.get("gasLimitTransaction", 3000000),
            manual_gas_price=data.get("manualGasPrice")
        )


@dataclass
class SolanaNetworkConfig(BaseNetworkConfig):
    """Solana-specific network configuration."""
    confirm_retry_interval: float = 0.5
    confirm_retry_count: int = 10
    base_priority_fee_pct: int = 90

    @classmethod
    def from_dict(cls, data: Dict[str, Any], network: str) -> "SolanaNetworkConfig":
        """Create SolanaNetworkConfig from dictionary."""
        return cls(
            chain="solana",
            network=network,
            node_url=data.get("nodeURL", ""),
            native_currency_symbol=data.get("nativeCurrencySymbol", "SOL"),
            default_compute_units=data.get("defaultComputeUnits", 200000),
            gas_estimate_interval=data.get("gasEstimateInterval", 60),
            max_fee=data.get("maxFee", 0.01),
            min_fee=data.get("minFee", 0.0001),
            retry_count=data.get("retryCount", 3),
            retry_fee_multiplier=data.get("retryFeeMultiplier", 2.0),
            retry_interval=data.get("retryInterval", 2),
            confirm_retry_interval=data.get("confirmRetryInterval", 0.5),
            confirm_retry_count=data.get("confirmRetryCount", 10),
            base_priority_fee_pct=data.get("basePriorityFeePct", 90)
        )


# Type alias for any network config
NetworkConfig = Union[EthereumNetworkConfig, SolanaNetworkConfig]


def create_network_config(chain: str, network: str, data: Dict[str, Any]) -> NetworkConfig:
    """
    Factory function to create appropriate network config based on chain.

    :param chain: Chain name (ethereum or solana)
    :param network: Network name
    :param data: Configuration data from Gateway
    :return: Appropriate NetworkConfig instance
    """
    if chain.lower() == "ethereum":
        return EthereumNetworkConfig.from_dict(data, network)
    elif chain.lower() == "solana":
        return SolanaNetworkConfig.from_dict(data, network)
    else:
        # For unknown chains, return base config
        return BaseNetworkConfig(
            chain=chain,
            network=network,
            node_url=data.get("nodeURL", ""),
            native_currency_symbol=data.get("nativeCurrencySymbol", ""),
            default_compute_units=data.get("defaultComputeUnits", 200000),
            gas_estimate_interval=data.get("gasEstimateInterval", 60),
            max_fee=data.get("maxFee", 0.01),
            min_fee=data.get("minFee", 0.0001),
            retry_count=data.get("retryCount", 3),
            retry_fee_multiplier=data.get("retryFeeMultiplier", 2.0),
            retry_interval=data.get("retryInterval", 2)
        )


@dataclass
class ConnectorConfig:
    """
    Unified configuration for a Gateway connector.
    Note: Connectors are inherently linked to specific chains (e.g., raydium is Solana-only).
    """
    name: str
    chain: str
    network: str
    trading_types: List[TradingType] = field(default_factory=list)
    wallet_address: Optional[str] = None
    network_config: Optional[NetworkConfig] = None

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

        :param client: GatewayClient instance
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

        # Get network config using determined chain
        network_data = await client.get_network_config(chain, network)
        network_config = create_network_config(chain, network, network_data)

        # Get wallet address if not provided
        if not wallet_address:
            wallets = await client.get_wallets(chain)
            if wallets and wallets[0].get("walletAddresses"):
                wallet_address = wallets[0]["walletAddresses"][0]

        return cls(
            name=connector_name,
            chain=chain,
            network=network,
            trading_types=trading_types,
            wallet_address=wallet_address,
            network_config=network_config
        )
