from decimal import Decimal

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0"),
    buy_percent_fee_deducted_from_returns=True,
)

CENTRALIZED = False

EXAMPLE_PAIR = "BTC-1H"

BROKER_ID = "HBOT"


class LimitlessConfigMap(BaseConnectorConfigMap):
    connector: str = "limitless"
    limitless_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Limitless API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    limitless_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Ethereum wallet private key (for EIP-712 order signing)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    model_config = ConfigDict(title="limitless")


KEYS = LimitlessConfigMap.model_construct()

OTHER_DOMAINS = []
OTHER_DOMAINS_PARAMETER = {}
OTHER_DOMAINS_EXAMPLE_PAIR = {}
OTHER_DOMAINS_DEFAULT_FEES = {}
OTHER_DOMAINS_KEYS = {}
