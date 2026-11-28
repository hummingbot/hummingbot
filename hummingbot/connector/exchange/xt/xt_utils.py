from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.002"),
    taker_percent_fee_decimal=Decimal("0.002"),
    buy_percent_fee_deducted_from_returns=True,
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    # Active API markets can report empty capabilities or openapiEnabled=False.
    # Discover trading markets; authenticated responses enforce API permissions.
    return (
        exchange_info.get("state") == "ONLINE"
        and exchange_info.get("tradingEnabled") is True
    )


class XtConfigMap(BaseConnectorConfigMap):
    connector: str = "xt"
    xt_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your XT API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    xt_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your XT API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    model_config = ConfigDict(title="xt")


KEYS = XtConfigMap.model_construct()
