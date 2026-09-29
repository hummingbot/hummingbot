from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.connector.exchange.bitget_unified import bitget_unified_constants as CONSTANTS
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# BitgetUnified fees: https://www.bitget.com/en/rate?tab=1

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
    symbol = bool(exchange_info.get("symbol"))
    # V3 instruments reports the listing state in "status"; only an online instrument accepts
    # orders, so a suspended or delisted pair must not reach the symbol map or the trading rules.
    online = exchange_info.get("status") == CONSTANTS.INSTRUMENT_STATUS_ONLINE

    return symbol and online


class BitgetUnifiedConfigMap(BaseConnectorConfigMap):
    connector: str = "bitget_unified"
    bitget_unified_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Bitget Unified API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    bitget_unified_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Bitget Unified secret key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    bitget_unified_passphrase: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Bitget Unified passphrase",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="bitget_unified")


KEYS = BitgetUnifiedConfigMap.model_construct()
