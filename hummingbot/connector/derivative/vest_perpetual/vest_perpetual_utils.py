"""
Vest Perpetual utility functions for symbol/pair conversions and config.
"""
from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Default fees (can be overridden by exchange info)
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0001"),
    taker_percent_fee_decimal=Decimal("0.0001"),
)

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-PERP"


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if the exchange information is valid.
    :param exchange_info: the exchange information dict
    :return: True if valid, False otherwise
    """
    symbols = exchange_info.get("symbols", [])
    return len(symbols) > 0


def convert_from_exchange_trading_pair(exchange_symbol: str) -> str:
    """
    Converts exchange symbol to Hummingbot trading pair format.
    For Vest: BTC-PERP, ETH-PERP, SOL-PERP -> BTC-PERP, ETH-PERP, SOL-PERP (no conversion needed)
    For equities: AAPL-USD-PERP -> AAPL-USD-PERP

    :param exchange_symbol: The exchange symbol (e.g. "BTC-PERP")
    :return: Hummingbot trading pair (e.g. "BTC-PERP")
    """
    return exchange_symbol


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    """
    Converts Hummingbot trading pair to exchange symbol.

    :param hb_trading_pair: The Hummingbot trading pair (e.g. "BTC-PERP")
    :return: Exchange symbol (e.g. "BTC-PERP")
    """
    return hb_trading_pair


class VestPerpetualConfigMap(BaseConnectorConfigMap):
    """
    Configuration map for Vest Perpetual connector.
    """
    connector: str = Field(default="vest_perpetual", client_data=None)

    vest_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Vest Perpetual API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    vest_perpetual_signing_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Vest Perpetual signing private key (0x...)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    vest_perpetual_account_group: int = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Vest Perpetual account group (integer)",
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    vest_perpetual_use_testnet: bool = Field(
        default=False,
        client_data=ClientFieldData(
            prompt=lambda cm: "Use Vest testnet? (True/False)",
            is_connect_key=False,
            prompt_on_new=False,
        )
    )

    class Config:
        title = "vest_perpetual"


KEYS = VestPerpetualConfigMap.construct()


def get_rest_url(use_testnet: bool = False) -> str:
    """Get the REST API URL based on environment."""
    from hummingbot.connector.derivative.vest_perpetual.vest_perpetual_constants import (
        REST_URL_DEV,
        REST_URL_PROD,
    )
    return REST_URL_DEV if use_testnet else REST_URL_PROD


def get_wss_url(use_testnet: bool = False) -> str:
    """Get the WebSocket URL based on environment."""
    from hummingbot.connector.derivative.vest_perpetual.vest_perpetual_constants import (
        WSS_URL_DEV,
        WSS_URL_PROD,
    )
    return WSS_URL_DEV if use_testnet else WSS_URL_PROD


def get_verifying_contract(use_testnet: bool = False) -> str:
    """Get the verifying contract address based on environment."""
    from hummingbot.connector.derivative.vest_perpetual.vest_perpetual_constants import (
        VERIFYING_CONTRACT_DEV,
        VERIFYING_CONTRACT_PROD,
    )
    return VERIFYING_CONTRACT_DEV if use_testnet else VERIFYING_CONTRACT_PROD
