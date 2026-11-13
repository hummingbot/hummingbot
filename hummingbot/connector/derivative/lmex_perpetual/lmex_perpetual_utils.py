from decimal import Decimal

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"

# LMEX Futures maker/taker fees (0.1%)
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
)


class LmexPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "lmex_perpetual"

    lmex_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your LMEX Perpetual API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    lmex_perpetual_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your LMEX Perpetual API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    lmex_perpetual_domain: str = Field(
        default="lmex_perpetual",
        json_schema_extra={
            "prompt": "Enter domain (lmex_perpetual for live, lmex_perpetual_testnet for sandbox)",
            "prompt_on_new": False,
        },
    )

    model_config = ConfigDict(title="lmex_perpetual")


KEYS = LmexPerpetualConfigMap.model_construct()
