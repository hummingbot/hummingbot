from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("showStatus") is True


class BybitConfigMap(BaseConnectorConfigMap):
    connector: str = "bybit"
    bybit_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Bybit API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    bybit_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Bybit API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="bybit")


KEYS = BybitConfigMap.model_construct()

OTHER_DOMAINS = ["bybit_testnet"]
OTHER_DOMAINS_PARAMETER = {"bybit_testnet": "bybit_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"bybit_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"bybit_testnet": DEFAULT_FEES}


class BybitTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "bybit_testnet"
    bybit_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Bybit Testnet API Key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    bybit_testnet_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Bybit Testnet API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="bybit_testnet")


OTHER_DOMAINS_KEYS = {"bybit_testnet": BybitTestnetConfigMap.model_construct()}
