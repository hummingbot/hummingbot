from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0004"),
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"

BROKER_ID = "hummingbot"


class GRVTPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "grvt_perpetual"
    grvt_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your GRVT Perpetual API key",
            "is_secure": True, "is_connect_key": True, "prompt_on_new": True}
    )
    grvt_perpetual_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your GRVT Perpetual API secret",
            "is_secure": True, "is_connect_key": True, "prompt_on_new": True}
    )


KEYS = GRVTPerpetualConfigMap.model_construct()

OTHER_DOMAINS = ["grvt_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"grvt_perpetual_testnet": "grvt_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"grvt_perpetual_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"grvt_perpetual_testnet": [0.02, 0.04]}


class GRVTPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "grvt_perpetual_testnet"
    grvt_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your GRVT Perpetual testnet API key",
            "is_secure": True, "is_connect_key": True, "prompt_on_new": True}
    )
    grvt_perpetual_testnet_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your GRVT Perpetual testnet API secret",
            "is_secure": True, "is_connect_key": True, "prompt_on_new": True}
    )


OTHER_DOMAINS_KEYS = {"grvt_perpetual_testnet": GRVTPerpetualTestnetConfigMap.model_construct()}

KEY_TO_ALLOWLIST = {
    "grvt_perpetual_api_key",
    "grvt_perpetual_api_secret",
}
