from decimal import Decimal
from typing import Optional

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0"),
    buy_percent_fee_deducted_from_returns=True,
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"

BROKER_ID = "HBOT"


class GRVTPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "grvt_perpetual"

    grvt_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your GRVT API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    grvt_perpetual_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your GRVT private key (used for EIP-712 signing)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    grvt_perpetual_sub_account_id: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your GRVT subaccount ID",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    model_config = ConfigDict(title="grvt_perpetual")


KEYS = GRVTPerpetualConfigMap.model_construct()

OTHER_DOMAINS = ["grvt_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"grvt_perpetual_testnet": "grvt_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"grvt_perpetual_testnet": EXAMPLE_PAIR}
OTHER_DOMAINS_DEFAULT_FEES = {"grvt_perpetual_testnet": [0, 0]}


class GRVTPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "grvt_perpetual_testnet"

    grvt_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your GRVT TESTNET API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    grvt_perpetual_testnet_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your GRVT TESTNET private key (used for EIP-712 signing)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    grvt_perpetual_testnet_sub_account_id: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your GRVT TESTNET subaccount ID",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    model_config = ConfigDict(title="grvt_perpetual_testnet")


OTHER_DOMAINS_KEYS = {
    "grvt_perpetual_testnet": GRVTPerpetualTestnetConfigMap.model_construct(),
}
