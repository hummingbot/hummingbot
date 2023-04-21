from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0005"),
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"

BROKER_ID = "x-3QreWesy"


class BitComPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="bit_com_perpetual", client_data=None)
    bit_com_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your BitCom Perpetual API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    bit_com_perpetual_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your BitCom Perpetual API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )


KEYS = BitComPerpetualConfigMap.construct()

OTHER_DOMAINS = ["bit_com_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"bit_com_perpetual_testnet": "bit_com_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"bit_com_perpetual_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"bit_com_perpetual_testnet": [0.02, 0.05]}


class BitComPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="bit_com_perpetual_testnet", client_data=None)
    bit_com_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your BitCom Perpetual testnet API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    bit_com_perpetual_testnet_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your BitCom Perpetual testnet API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "bit_com_perpetual"


OTHER_DOMAINS_KEYS = {"bit_com_perpetual_testnet": BitComPerpetualTestnetConfigMap.construct()}
