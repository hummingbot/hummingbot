from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0004"),
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"

BROKER_ID = "x-3QreWesy"


class HashkeyPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="hashkey_perpetual", client_data=None)
    hashkey_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Hashkey Perpetual API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    hashkey_perpetual_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Hashkey Perpetual API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )


KEYS = HashkeyPerpetualConfigMap.construct()

OTHER_DOMAINS = ["hashkey_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"hashkey_perpetual_testnet": "hashkey_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"hashkey_perpetual_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"hashkey_perpetual_testnet": [0.02, 0.04]}


class HashkeyPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="hashkey_perpetual_testnet", client_data=None)
    hashkey_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Hashkey Perpetual testnet API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    hashkey_perpetual_testnet_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Hashkey Perpetual testnet API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "hashkey_perpetual"


OTHER_DOMAINS_KEYS = {"hashkey_perpetual_testnet": HashkeyPerpetualTestnetConfigMap.construct()}
