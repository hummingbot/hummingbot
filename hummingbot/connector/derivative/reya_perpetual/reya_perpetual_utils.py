from decimal import Decimal

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = False
EXAMPLE_PAIR = "BTC-RUSD"
DEFAULT_FEES = TradeFeeSchema(maker_percent_fee_decimal=Decimal("0"), taker_percent_fee_decimal=Decimal("0.0003"))

PRIVATE_KEY_PROMPT = "Enter the private key of your Reya signer (the owner wallet or one of its API wallets)"
WALLET_ADDRESS_PROMPT = "Enter the owner wallet address of the Reya account"
ACCOUNT_ID_PROMPT = "Enter the Reya perpetual account ID"


class ReyaPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "reya_perpetual"
    reya_perpetual_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={"prompt": PRIVATE_KEY_PROMPT, "is_secure": True, "is_connect_key": True,
                           "prompt_on_new": True},
    )
    reya_perpetual_wallet_address: SecretStr = Field(
        default=...,
        json_schema_extra={"prompt": WALLET_ADDRESS_PROMPT, "is_secure": False, "is_connect_key": True,
                           "prompt_on_new": True},
    )
    reya_perpetual_account_id: SecretStr = Field(
        default=...,
        json_schema_extra={"prompt": ACCOUNT_ID_PROMPT, "is_secure": False, "is_connect_key": True,
                           "prompt_on_new": True},
    )
    model_config = ConfigDict(title="reya_perpetual")


KEYS = ReyaPerpetualConfigMap.model_construct()

OTHER_DOMAINS = ["reya_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"reya_perpetual_testnet": "reya_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"reya_perpetual_testnet": "BTC-RUSD"}
OTHER_DOMAINS_DEFAULT_FEES = {"reya_perpetual_testnet": DEFAULT_FEES}


class ReyaPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "reya_perpetual_testnet"
    reya_perpetual_testnet_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={"prompt": PRIVATE_KEY_PROMPT, "is_secure": True, "is_connect_key": True,
                           "prompt_on_new": True},
    )
    reya_perpetual_testnet_wallet_address: SecretStr = Field(
        default=...,
        json_schema_extra={"prompt": WALLET_ADDRESS_PROMPT, "is_secure": False, "is_connect_key": True,
                           "prompt_on_new": True},
    )
    reya_perpetual_testnet_account_id: SecretStr = Field(
        default=...,
        json_schema_extra={"prompt": ACCOUNT_ID_PROMPT, "is_secure": False, "is_connect_key": True,
                           "prompt_on_new": True},
    )
    model_config = ConfigDict(title="reya_perpetual_testnet")


OTHER_DOMAINS_KEYS = {"reya_perpetual_testnet": ReyaPerpetualTestnetConfigMap.model_construct()}
