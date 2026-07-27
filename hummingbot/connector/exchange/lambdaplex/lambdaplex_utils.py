from decimal import Decimal

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.connector.exchange.lambdaplex import lambdaplex_constants as CONSTANTS
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "HBAR-USDT"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.00120000"),
    taker_percent_fee_decimal=Decimal("0.00250000"),
    buy_percent_fee_deducted_from_returns=True,
)


class LambdaplexConfigMap(BaseConnectorConfigMap):
    connector: str = CONSTANTS.EXCHANGE_NAME
    lambdaplex_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your Lambdaplex API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    lambdaplex_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your Lambdaplex private (unencypted) key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title=CONSTANTS.EXCHANGE_NAME)


KEYS = LambdaplexConfigMap.model_construct()
