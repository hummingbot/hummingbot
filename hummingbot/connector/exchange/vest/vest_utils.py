from decimal import Decimal
from typing import Any, Dict, Literal

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Conservative fee estimate - will need to be updated based on actual Vest fees
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0005"),
    taker_percent_fee_decimal=Decimal("0.001"),
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USD"  # Using standard format for Hummingbot compatibility


class VestConfigMap(BaseConnectorConfigMap):
    connector: str = "vest"
    vest_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Vest Markets API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    vest_primary_address: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Vest Markets primary address (account holding balances)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    vest_signing_address: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Vest Markets signing address (delegate signing key)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    vest_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Vest Markets private key for signing",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    vest_environment: Literal["prod", "dev"] = Field(
        default="prod",
        json_schema_extra={
            "prompt": "Which Vest Markets environment to use? (prod/dev)",
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )

    model_config = ConfigDict(title="vest")


KEYS = VestConfigMap.model_construct()


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    # Check if trading is enabled
    if exchange_info.get("status") != "TRADING":
        return False

    # Check if symbol exists
    symbol = exchange_info.get("symbol", "")
    if not symbol:
        return False

    # For VEST, validate based on available fields
    # Priority: use base/quote if available, otherwise rely on symbol format
    if "base" in exchange_info and "quote" in exchange_info:
        return (exchange_info.get("base", "") != "" and
                exchange_info.get("quote", "") != "")
    elif "baseAsset" in exchange_info and "quoteAsset" in exchange_info:
        return (exchange_info.get("baseAsset", "") != "" and
                exchange_info.get("quoteAsset", "") != "")
    else:
        # Fallback: validate symbol format
        return _is_valid_vest_symbol_format(symbol)


def _is_valid_vest_symbol_format(symbol: str) -> bool:
    """
    Validate VEST symbol format (e.g., BTC-PERP, ETH-USD-PERP, BTC-USDT)

    :param symbol: The trading symbol to validate
    :return: True if symbol format is valid, False otherwise
    """
    if not symbol or "-" not in symbol:
        return False

    # Valid VEST symbol patterns
    if symbol.endswith("-PERP"):
        # Perpetual contracts: BTC-PERP, ETH-USD-PERP
        base_part = symbol[:-5]  # Remove "-PERP"
        if not base_part:
            return False
        parts = base_part.split("-")
        return len(parts) >= 1 and all(part.isalpha() for part in parts)
    else:
        # Spot pairs: BTC-USDT, ETH-USD
        parts = symbol.split("-")
        return len(parts) >= 2 and all(part.isalpha() for part in parts)
