from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Maker rebates(-0.02%) are paid out continuously on each trade directly to the trading wallet.(https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees)
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0.00025"),
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USD"

BROKER_ID = "HBOT"


class HyperliquidPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="hyperliquid_perpetual", client_data=None)
    hyperliquid_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Arbitrum wallet public key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    hyperliquid_perpetual_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Arbitrum wallet private key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )


KEYS = HyperliquidPerpetualConfigMap.construct()

OTHER_DOMAINS = ["hyperliquid_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"hyperliquid_perpetual_testnet": "hyperliquid_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"hyperliquid_perpetual_testnet": "BTC-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"hyperliquid_perpetual_testnet": [0, 0.025]}


class HyperliquidPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="hyperliquid_perpetual_testnet", client_data=None)
    hyperliquid_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Arbitrum wallet address",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    hyperliquid_perpetual_testnet_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Arbitrum wallet private key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "hyperliquid_perpetual"


OTHER_DOMAINS_KEYS = {"hyperliquid_perpetual_testnet": HyperliquidPerpetualTestnetConfigMap.construct()}
