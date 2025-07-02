"""
Gateway connector package for Hummingbot.

This package provides a unified interface for connecting to blockchain DEXs
through the Gateway service. It supports multiple trading types (swap, AMM, CLMM)
and multiple chains (Ethereum, Solana).
"""

# Core components
from .core import GatewayClient, GatewayConnector

# Models
from .models import (
    BaseNetworkConfig,
    ConnectorConfig,
    EthereumNetworkConfig,
    GatewayInFlightOrder,
    GatewayInFlightPosition,
    NetworkConfig,
    PoolInfo,
    Position,
    PriceQuote,
    SolanaNetworkConfig,
    TokenInfo,
    TradingType,
    TransactionResult,
    TransactionStatus,
    create_network_config,
)

# Trading type handlers
from .trading_types import AMMHandler, CLMMHandler, SwapHandler

# Utilities
from .utils import (
    GatewayConnectorFactory,
    calculate_price_from_amounts,
    estimate_transaction_fee,
    format_trading_pair,
    get_connector_base_name,
    get_connector_trading_type,
    is_connector_compatible,
    parse_connector_trading_pair,
    validate_wallet_address,
)

__all__ = [
    # Core
    "GatewayClient",
    "GatewayConnector",
    # Models
    "BaseNetworkConfig",
    "ConnectorConfig",
    "EthereumNetworkConfig",
    "GatewayInFlightOrder",
    "GatewayInFlightPosition",
    "NetworkConfig",
    "PoolInfo",
    "Position",
    "PriceQuote",
    "SolanaNetworkConfig",
    "TokenInfo",
    "TradingType",
    "TransactionResult",
    "TransactionStatus",
    "create_network_config",
    # Trading handlers
    "AMMHandler",
    "CLMMHandler",
    "SwapHandler",
    # Utils
    "GatewayConnectorFactory",
    "calculate_price_from_amounts",
    "estimate_transaction_fee",
    "format_trading_pair",
    "get_connector_base_name",
    "get_connector_trading_type",
    "is_connector_compatible",
    "parse_connector_trading_pair",
    "validate_wallet_address",
]

# Version
__version__ = "2.0.0"
