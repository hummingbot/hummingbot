from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema


CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USD"
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),  # 0.02%
    taker_percent_fee_decimal=Decimal("0.0005"),  # 0.05%
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
    parts = trading_pair.split("-")
    if len(parts) == 2:
        return parts[0], parts[1]
    return trading_pair, "USD"


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    """
    Convert exchange symbol format to Hummingbot format.
    """
    # Architect uses formats like "BTC-USD-PERP" or "BTC_USD"
    if "-PERP" in exchange_trading_pair:
        exchange_trading_pair = exchange_trading_pair.replace("-PERP", "")
    return exchange_trading_pair.replace("_", "-")


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    """
    Convert Hummingbot format to exchange symbol format.
    """
    # Add -PERP suffix for perpetual contracts
    base, quote = split_trading_pair(hb_trading_pair)
    return f"{base}-{quote}-PERP"


class ArchitectPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="architect_perpetual", const=True, client_data=None)
    architect_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Architect Perpetual API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    architect_perpetual_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Architect Perpetual API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "architect_perpetual"


KEYS = ArchitectPerpetualConfigMap.construct()
