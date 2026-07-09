from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0005"),
    buy_percent_fee_deducted_from_returns=False,
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    return exchange_info.get("kind") == "PERPETUAL"


class GrvtPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "grvt_perpetual"
    grvt_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your GRVT API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    grvt_perpetual_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your GRVT private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    grvt_perpetual_trading_account_id: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your GRVT trading account ID",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    model_config = ConfigDict(title="grvt_perpetual")


KEYS = GrvtPerpetualConfigMap.model_construct()

OTHER_DOMAINS = ["grvt_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"grvt_perpetual_testnet": "grvt_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"grvt_perpetual_testnet": EXAMPLE_PAIR}
OTHER_DOMAINS_DEFAULT_FEES = {"grvt_perpetual_testnet": DEFAULT_FEES}


class GrvtPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "grvt_perpetual_testnet"
    grvt_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your GRVT Testnet API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    grvt_perpetual_testnet_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your GRVT Testnet private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    grvt_perpetual_testnet_trading_account_id: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your GRVT Testnet trading account ID",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    model_config = ConfigDict(title="grvt_perpetual_testnet")


OTHER_DOMAINS_KEYS = {
    "grvt_perpetual_testnet": GrvtPerpetualTestnetConfigMap.model_construct(),
}
