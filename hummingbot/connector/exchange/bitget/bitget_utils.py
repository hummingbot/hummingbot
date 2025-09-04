from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr
import random
from hummingbot.connector.exchange.bitget.bitget_constants import MAX_ORDER_ID_LEN
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0001"),
    taker_percent_fee_decimal=Decimal("0.0001"),
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    symbol = exchange_info.get("symbol")

    return symbol is not None


def generate_id() -> int:
    return str(random.randint(0, 10 ** MAX_ORDER_ID_LEN))


class BitgetConfigMap(BaseConnectorConfigMap):
    connector: str = "bitget"
    bitget_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Bitget API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    bitget_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Bitget secret key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    bitget_passphrase: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Bitget passphrase",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="bitget")


KEYS = BitgetConfigMap.construct()
