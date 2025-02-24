from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Maker rebates(-0.02%) are paid out continuously on each trade directly to the trading wallet.(https://derive_perpetual.gitbook.io/derive_perpetual-docs/trading/fees)
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.01"),
    taker_percent_fee_decimal=Decimal("0.03"),
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = False

EXAMPLE_PAIR = "OP-USDC"

BROKER_ID = "HBOT"


class DerivePerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="derive_perpetual", client_data=None)
    derive_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter Your DerivePerpetual Wallet address",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    derive_perpetual_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your wallet private key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    sub_id: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Subaccount ID",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )


KEYS = DerivePerpetualConfigMap.construct()

OTHER_DOMAINS = ["derive_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"derive_perpetual_testnet": "derive_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"derive_perpetual_testnet": "BTC-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"derive_perpetual_testnet": [0, 0.025]}


class DerivePerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="derive_perpetual_testnet", client_data=None)
    derive_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter Your DerivePerpetual Wallet address",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    derive_perpetual_testnet_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your wallet private key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    sub_id: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Subaccount Id",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "derive_perpetual"


OTHER_DOMAINS_KEYS = {"derive_perpetual_testnet": DerivePerpetualTestnetConfigMap.construct()}
