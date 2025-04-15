from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "AVAX-USDC"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.0012"),
    buy_percent_fee_deducted_from_returns=True
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("allowswap", None) is True


class DexalotConfigMap(BaseConnectorConfigMap):
    connector: str = "dexalot"
    dexalot_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Dexalot private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    dexalot_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Dexalot wallet address",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="dexalot")


KEYS = DexalotConfigMap.model_construct()

OTHER_DOMAINS = ["dexalot_testnet"]
OTHER_DOMAINS_PARAMETER = {"dexalot_testnet": "dexalot_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"dexalot_testnet": "AVAX-USDC"}
OTHER_DOMAINS_DEFAULT_FEES = {"dexalot_testnet": [0, 0.025]}


class DexalotTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "dexalot_testnet"
    dexalot_testnet_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Dexalot private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    dexalot_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Dexalot wallet address",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="dexalot_testnet")


OTHER_DOMAINS_KEYS = {"dexalot_testnet": DexalotTestnetConfigMap.model_construct()}
