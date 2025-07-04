from decimal import Decimal

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0004"),
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"

BROKER_ID = "x-3QreWesy"


class BinancePerpetual2ConfigMap(BaseConnectorConfigMap):
    connector: str = "binance_perpetual_2"
    binance_perpetual_2_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your second Binance Perpetual API key",
            "is_secure": True, "is_connect_key": True, "prompt_on_new": True}
    )
    binance_perpetual_2_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your second Binance Perpetual API secret",
            "is_secure": True, "is_connect_key": True, "prompt_on_new": True}
    )


KEYS = BinancePerpetual2ConfigMap.model_construct()

OTHER_DOMAINS = ["binance_perpetual_2_testnet"]
OTHER_DOMAINS_PARAMETER = {"binance_perpetual_2_testnet": "binance_perpetual_2_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"binance_perpetual_2_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"binance_perpetual_2_testnet": [0.02, 0.04]}


class BinancePerpetual2TestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "binance_perpetual_2_testnet"
    binance_perpetual_2_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your second Binance Perpetual testnet API key",
            "is_secure": True, "is_connect_key": True, "prompt_on_new": True}
    )
    binance_perpetual_2_testnet_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your second Binance Perpetual testnet API secret",
            "is_secure": True, "is_connect_key": True, "prompt_on_new": True}
    )
    model_config = ConfigDict(title="binance_perpetual_2")


OTHER_DOMAINS_KEYS = {"binance_perpetual_2_testnet": BinancePerpetual2TestnetConfigMap.model_construct()} 