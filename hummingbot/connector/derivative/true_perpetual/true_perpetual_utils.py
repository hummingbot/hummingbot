from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# TRUE perps: maker 200 ppm (0.02%), taker 650 ppm (0.065%). Live values come from /markets.
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.00065"),
    buy_percent_fee_deducted_from_returns=True,
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDC"


class TruePerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "true_perpetual"
    true_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your TRUE bot key id (tbk_...), created in the Bots tab at app.truefinance.ai/bots",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    true_perpetual_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your TRUE bot key secret (tbs_..., shown once when the key is created)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )


KEYS = TruePerpetualConfigMap.model_construct()
