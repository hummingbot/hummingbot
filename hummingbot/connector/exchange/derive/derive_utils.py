from decimal import Decimal

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Maker rebates(-0.02%) are paid out continuously on each trade directly to the trading wallet.(https://derive.gitbook.io/derive-docs/trading/fees)
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.01"),
    taker_percent_fee_decimal=Decimal("0.03"),
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = False

EXAMPLE_PAIR = "OP-USDC"

BROKER_ID = "HBOT"


class DeriveConfigMap(BaseConnectorConfigMap):
    connector: str = "derive"
    derive_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Derive Wallet address",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    derive_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your wallet private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    sub_id: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Subaccount Id",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    account_type: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Derive Account Type (trader/market_maker)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )


KEYS = DeriveConfigMap.model_construct()

OTHER_DOMAINS = ["derive_testnet"]
OTHER_DOMAINS_PARAMETER = {"derive_testnet": "derive_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"derive_testnet": "BTC-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"derive_testnet": [0, 0.025]}


class DeriveTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "derive_testnet"
    derive_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Derive Wallet address",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    derive_testnet_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your wallet private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    sub_id: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Subaccount Id",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    account_type: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Derive Account Type (trader/market_maker)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="derive")


OTHER_DOMAINS_KEYS = {"derive_testnet": DeriveTestnetConfigMap.model_construct()}
