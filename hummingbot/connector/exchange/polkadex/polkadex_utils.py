from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "PDEX-1"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0"),
)


def normalized_asset_name(asset_id: str, asset_name: str) -> str:
    name = asset_name if asset_id.isdigit() else asset_id
    name = name.replace("CHAINBRIDGE-", "C")
    name = name.replace("TEST DEX", "TDEX")
    name = name.replace("TEST BRIDGE", "TBRI")
    return name


class PolkadexConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="polkadex", const=True, client_data=None)
    polkadex_seed_phrase: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Polkadex seed phrase",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "polkadex"


KEYS = PolkadexConfigMap.construct()

# Disabling testnet because it breaks. We should enable it back when the issues in the server are solved
# OTHER_DOMAINS = ["polkadex_testnet"]
OTHER_DOMAINS = []
OTHER_DOMAINS_PARAMETER = {"polkadex_testnet": "testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"polkadex_testnet": EXAMPLE_PAIR}
OTHER_DOMAINS_DEFAULT_FEES = {"polkadex_testnet": DEFAULT_FEES}


class PolkadexTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="polkadex_testnet", const=True, client_data=None)
    polkadex_seed_phrase: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Polkadex testnet seed phrase",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "polkadex_testnet"


OTHER_DOMAINS_KEYS = {"polkadex_testnet": PolkadexTestnetConfigMap.construct()}
