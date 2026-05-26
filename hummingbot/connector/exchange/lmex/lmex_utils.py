from decimal import Decimal

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.connector.exchange.lmex import lmex_constants as CONSTANTS
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"

# LMEX default fees: 0.1% maker / 0.1% taker
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
)


class LmexConfigMap(BaseConnectorConfigMap):
    connector: str = "lmex"
    lmex_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: f"Enter your {CONSTANTS.EXCHANGE_NAME} API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    lmex_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: f"Enter your {CONSTANTS.EXCHANGE_NAME} secret key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    lmex_domain: str = Field(
        default=CONSTANTS.DEFAULT_DOMAIN,
        json_schema_extra={
            "prompt": lambda cm: (
                f"Enter domain for {CONSTANTS.EXCHANGE_NAME} "
                f"(leave blank for production, enter 'sandbox' for test environment)"
            ),
            "prompt_on_new": False,
        },
    )
    model_config = ConfigDict(title="lmex")


KEYS = LmexConfigMap.model_construct()
