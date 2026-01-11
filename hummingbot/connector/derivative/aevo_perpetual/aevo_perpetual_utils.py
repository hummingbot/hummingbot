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
EXAMPLE_PAIR = "ETH-PERP"
BROKER_ID = "HBOT"


class AevoPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "aevo_perpetual"
    aevo_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Aevo Perpetual API key",
            "is_secure": True, "is_connect_key": True, "prompt_on_new": True}
    )
    aevo_perpetual_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Aevo Perpetual API secret",
            "is_secure": True, "is_connect_key": True, "prompt_on_new": True}
    )


KEYS = AevoPerpetualConfigMap.model_construct()

OTHER_DOMAINS = ["aevo_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"aevo_perpetual_testnet": "aevo_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"aevo_perpetual_testnet": "ETH-PERP"}
OTHER_DOMAINS_DEFAULT_FEES = {"aevo_perpetual_testnet": DEFAULT_FEES}


class AevoPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "aevo_perpetual_testnet"
    aevo_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Aevo Perpetual testnet API key",
            "is_secure": True, "is_connect_key": True, "prompt_on_new": True}
    )
    aevo_perpetual_testnet_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Aevo Perpetual testnet API secret",
            "is_secure": True, "is_connect_key": True, "prompt_on_new": True}
    )


OTHER_DOMAINS_KEYS = {"aevo_perpetual_testnet": AevoPerpetualTestnetConfigMap.model_construct()}
