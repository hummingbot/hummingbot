from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0005"),
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"
BROKER_ID = "HBOT"


class EvedexPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "evedex_perpetual"
    evedex_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your EVEDEX API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    evedex_perpetual_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your EVEDEX wallet private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )


KEYS = EvedexPerpetualConfigMap.model_construct()

OTHER_DOMAINS = ["evedex_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"evedex_perpetual_testnet": "evedex_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"evedex_perpetual_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"evedex_perpetual_testnet": [0.02, 0.05]}


class EvedexPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "evedex_perpetual_testnet"
    evedex_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your EVEDEX testnet API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    evedex_perpetual_testnet_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your EVEDEX testnet wallet private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )


OTHER_DOMAINS_KEYS = {
    "evedex_perpetual_testnet": EvedexPerpetualTestnetConfigMap.model_construct()
}
