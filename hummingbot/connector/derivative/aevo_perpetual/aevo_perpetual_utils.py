from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "ETH-PERP"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),  # 0.02%
    taker_percent_fee_decimal=Decimal("0.0005"),  # 0.05%
    buy_percent_fee_deducted_from_returns=False,
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Validates the exchange information response.
    """
    return exchange_info is not None and len(exchange_info) > 0


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    """
    Converts an exchange trading pair to Hummingbot format.
    Aevo uses format like "ETH-PERP" which maps to "ETH-USD"
    """
    if "-PERP" in exchange_trading_pair:
        base = exchange_trading_pair.replace("-PERP", "")
        return f"{base}-USD"
    return exchange_trading_pair


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    """
    Converts a Hummingbot trading pair to exchange format.
    """
    if "-USD" in hb_trading_pair:
        base = hb_trading_pair.replace("-USD", "")
        return f"{base}-PERP"
    return hb_trading_pair


def get_pair_specific_data(trading_pair: str, exchange_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Retrieves pair-specific data from exchange info.
    """
    exchange_pair = convert_to_exchange_trading_pair(trading_pair)
    for market in exchange_info:
        if market.get("instrument_name") == exchange_pair:
            return market
    return None


def decimal_to_padded_int(value: Decimal, decimals: int = 6) -> int:
    """
    Converts a decimal value to an integer with padding.
    Aevo uses 6 decimal places for prices.
    """
    return int(value * Decimal(10 ** decimals))


def padded_int_to_decimal(value: int, decimals: int = 6) -> Decimal:
    """
    Converts a padded integer back to decimal.
    """
    return Decimal(value) / Decimal(10 ** decimals)


class AevoPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="aevo_perpetual", const=True, client_data=None)
    aevo_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Aevo API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    aevo_perpetual_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Aevo API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    aevo_perpetual_signing_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Aevo signing key (private key for order signing)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "aevo_perpetual"


KEYS = AevoPerpetualConfigMap.construct()
