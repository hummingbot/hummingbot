from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "FLIP_USDT"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0"),
)

class ChainflipLpConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="chainflip_lp", const=True, client_data=None)
    chainflip_lp_api_url: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Chainflip LP API RPC Node Url (e.g http://localhost:10589)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    chainflip_lp_seed_phrase: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Chainflip LP Wallet Seed Phrase",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "chainflip_lp"

KEYS = ChainflipLpConfigMap.construct()

OTHER_DOMAINS = ["chainflip_lp_testnet"]
OTHER_DOMAINS_PARAMETER = {"chainflip_lp_testnet": "testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"chainflip_lp_testnet": "sFLIP-sUSDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"chainflip_lp_testnet": DEFAULT_FEES}



class ChainflipLpTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="chainflip_lp_testnet", const=True, client_data=None)
    chainflip_lp_api_url: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Chainflip LP Testnet API RPC Node Url (e.g http://localhost:10589)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    chainflip_lp_seed_phrase: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Chainflip LP Wallet Seed Phrase",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "chainflip_lp_testnet"


OTHER_DOMAINS_KEYS = {"chainflip_lp_testnet": ChainflipLpTestnetConfigMap.construct()}

