import time
from decimal import Decimal
from typing import Optional

from kuru_sdk_py.configs import ConfigManager, MarketConfig
from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.connector.exchange.kuru import kuru_constants as CONSTANTS
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# ----------------------------------------------------------------
# Registration constants (read by AllConnectorSettings auto-discovery)
# ----------------------------------------------------------------

CENTRALIZED = False  # Kuru is an on-chain DEX
EXAMPLE_PAIR = "MON-USDC"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0.001"),  # ~10 bps
)


class KuruConfigMap(BaseConnectorConfigMap):
    """Configuration for the Kuru connector."""

    connector: str = "kuru"

    kuru_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your wallet private key (with 0x prefix)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    kuru_market_address: str = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter the on-chain market contract address",
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    kuru_rpc_url: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "prompt": lambda cm: f"Enter HTTP RPC endpoint (leave blank for default: {CONSTANTS.DEFAULT_RPC_URL})",
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    kuru_rpc_ws_url: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "prompt": lambda cm: f"Enter WebSocket RPC endpoint (leave blank for default: {CONSTANTS.DEFAULT_RPC_WS_URL})",
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    kuru_ws_url: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "prompt": lambda cm: f"Enter Kuru orderbook WebSocket URL (leave blank for default: {CONSTANTS.DEFAULT_KURU_WS_URL})",
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    kuru_api_url: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "prompt": lambda cm: f"Enter Kuru REST API URL (leave blank for default: {CONSTANTS.DEFAULT_KURU_API_URL})",
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    model_config = ConfigDict(title="kuru")


KEYS = KuruConfigMap.model_construct()


# ----------------------------------------------------------------
# Utility functions
# ----------------------------------------------------------------


def get_market_config(market_address: str, rpc_url: Optional[str] = None) -> MarketConfig:
    """
    Get MarketConfig for a market address.

    Checks KNOWN_MARKETS first for cached config, falls back to
    fetching from chain for unknown addresses.
    """
    normalized = market_address.strip()

    # Check known markets (case-insensitive)
    for addr, config_dict in CONSTANTS.KNOWN_MARKETS.items():
        if addr.lower() == normalized.lower():
            return MarketConfig(**config_dict)

    # Unknown market - fetch from chain
    return ConfigManager.load_market_config(
        market_address=normalized,
        rpc_url=rpc_url or CONSTANTS.DEFAULT_RPC_URL,
    )


def trading_pair_from_market_config(market_config: MarketConfig) -> str:
    """Derive Hummingbot-style trading pair (e.g. 'MON-USDC') from MarketConfig."""
    return market_config.market_symbol


def get_current_server_time() -> float:
    """Return current time. DEX has no server time drift concern."""
    return time.time()
