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


class GrvtPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "grvt_perpetual"
    grvt_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your GRVT Perpetual API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    grvt_perpetual_sub_account_id: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your GRVT sub account ID (numeric string, e.g. '2927361478773809152')",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    grvt_perpetual_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your GRVT Ethereum signing private key (hex, e.g. 0x...)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )

    class Config:
        title = "grvt_perpetual"


KEYS = GrvtPerpetualConfigMap.model_construct()

OTHER_DOMAINS = ["grvt_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"grvt_perpetual_testnet": "grvt_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"grvt_perpetual_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"grvt_perpetual_testnet": [0.02, 0.05]}


class GrvtPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "grvt_perpetual_testnet"
    grvt_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your GRVT Perpetual testnet API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    grvt_perpetual_testnet_sub_account_id: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your GRVT testnet sub account ID",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    grvt_perpetual_testnet_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your GRVT testnet Ethereum signing private key (hex, e.g. 0x...)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )

    class Config:
        title = "grvt_perpetual_testnet"


OTHER_DOMAINS_KEYS = {"grvt_perpetual_testnet": GrvtPerpetualTestnetConfigMap.model_construct()}
