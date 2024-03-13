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

EXAMPLE_PAIR = "BTC-USDC"

BROKER_ID = ""


class VegaPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="vega_perpetual", client_data=None)
    vega_perpetual_public_key: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Vega public key (party id), NOTE: This is not your ETH public key!",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    vega_perpetual_seed_phrase: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter the seed phrase used with your Vega Wallet / Metamask Snap",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )


KEYS = VegaPerpetualConfigMap.construct()

OTHER_DOMAINS = ["vega_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"vega_perpetual_testnet": "vega_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"vega_perpetual_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"vega_perpetual_testnet": [0.02, 0.04]}


class VegaPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="vega_perpetual_testnet", client_data=None)
    vega_perpetual_testnet_public_key: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Vega public key (party id), NOTE: This is not your ETH public key!",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    vega_perpetual_testnet_seed_phrase: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter the seed phrase used with your Vega Wallet / Metamask Snap",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "vega_perpetual"


OTHER_DOMAINS_KEYS = {"vega_perpetual_testnet": VegaPerpetualTestnetConfigMap.construct()}
