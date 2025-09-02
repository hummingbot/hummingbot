"""
Utility functions and configuration for Polymarket connector.
"""

from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Connector settings
CENTRALIZED = False
EXAMPLE_PAIR = "ELECTION2024-YES-USDC"
USE_ETHEREUM_WALLET = False  # Handles Polygon wallet directly via SDK, not gateway
USE_ETH_GAS_LOOKUP = False

# Trading fee configuration
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.02"),  # 2% maker fee
    taker_percent_fee_decimal=Decimal("0.07"),  # 7% taker fee
    buy_percent_fee_deducted_from_returns=True
)


class PolymarketConfigMap(BaseConnectorConfigMap):
    connector: str = "polymarket"
    polymarket_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Polygon private key with 0x prefix",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    polymarket_wallet_address: str = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Polygon wallet address",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    polymarket_signature_type: int = Field(
        default=0,
        json_schema_extra={
            "prompt": "Enter signature type (0=EOA, 1=PROXY, 2=GNOSIS) [default: 0]",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )


KEYS = PolymarketConfigMap.model_construct()

# Domain configuration (Polymarket doesn't have multiple domains)
OTHER_DOMAINS = []
OTHER_DOMAINS_PARAMETER = {}
OTHER_DOMAINS_EXAMPLE_PAIR = {}
OTHER_DOMAINS_DEFAULT_FEES = {}
OTHER_DOMAINS_KEYS = {}
