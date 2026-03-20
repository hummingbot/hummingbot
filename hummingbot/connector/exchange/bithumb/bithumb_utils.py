from decimal import Decimal

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-KRW"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0025"),
    taker_percent_fee_decimal=Decimal("0.0025"),
)


class BithumbConfigMap(BaseConnectorConfigMap):
    connector: str = "bithumb"
    bithumb_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Bithumb API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    bithumb_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Bithumb secret key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    model_config = ConfigDict(title="bithumb")


KEYS = BithumbConfigMap.model_construct()
