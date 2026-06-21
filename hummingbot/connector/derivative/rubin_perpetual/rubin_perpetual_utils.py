from decimal import Decimal

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USD"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0001"),
    taker_percent_fee_decimal=Decimal("0.0005"),
)


def clamp(value, minvalue, maxvalue):
    return max(minvalue, min(value, maxvalue))


class RubinPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "rubin_perpetual"
    rubin_perpetual_secret_phrase: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Rubin secret phrase (24 words)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    rubin_perpetual_chain_address: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Rubin chain address ( starts with 'rit' )",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="rubin_perpetual")


KEYS = RubinPerpetualConfigMap.model_construct()
