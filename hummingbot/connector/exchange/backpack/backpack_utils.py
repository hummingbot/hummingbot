from decimal import Decimal
from typing import Any, Dict, Tuple

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema


CENTRALIZED = True
EXAMPLE_PAIR = "BTC_USDC"
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0008"),  # 0.08%
    taker_percent_fee_decimal=Decimal("0.0010"),  # 0.10%
    buy_percent_fee_deducted_from_returns=False,
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Validates exchange information response.
    """
    return exchange_info is not None and len(exchange_info) > 0


def split_trading_pair(trading_pair: str) -> Tuple[str, str]:
    """
    Split trading pair into base and quote assets.
    """
    if "_" in trading_pair:
        parts = trading_pair.split("_")
    else:
        parts = trading_pair.split("-")

    if len(parts) == 2:
        return parts[0], parts[1]
    return trading_pair, "USDC"


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    """
    Convert exchange symbol format to Hummingbot format.
    Backpack uses format like "BTC_USDC"
    """
    return exchange_trading_pair.replace("_", "-")


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    """
    Convert Hummingbot format to exchange symbol format.
    """
    return hb_trading_pair.replace("-", "_")


class BackpackConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="backpack", const=True, client_data=None)
    backpack_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Backpack API key (base64-encoded public key)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    backpack_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Backpack API secret (base64-encoded private key)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "backpack"


KEYS = BackpackConfigMap.construct()
