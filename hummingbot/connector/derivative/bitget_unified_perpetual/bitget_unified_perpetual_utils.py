from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.connector.derivative.bitget_unified_perpetual import bitget_unified_perpetual_constants as CONSTANTS
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# BitgetUnified fees: https://www.bitget.com/en/rate?tab=1

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.00036"),
    taker_percent_fee_decimal=Decimal("0.001"),
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    symbol = bool(exchange_info.get("symbol"))
    dated_futures = bool(exchange_info.get("deliveryPeriod"))

    return symbol and not dated_futures


def is_instrument_tradable(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if new orders may be placed on a trading pair based on its exchange information.

    This is deliberately narrower than :func:`is_exchange_information_valid`, which stays
    permissive so that the symbol map keeps covering every instrument. A contract that is
    suspended while the account still holds a position on it must remain resolvable, or position
    polling can no longer translate the symbol the exchange reports back to a trading pair.

    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair accepts new orders, False otherwise
    """
    # V3 instruments reports the listing state in "status"; only an online instrument accepts
    # orders. Withholding the trading rule is what stops orders being placed, since the connector
    # refuses to create an order for a pair that has no rule.
    online = exchange_info.get("status") == CONSTANTS.INSTRUMENT_STATUS_ONLINE

    return is_exchange_information_valid(exchange_info) and online


class BitgetUnifiedPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "bitget_unified_perpetual"
    bitget_unified_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Bitget Unified Perpetual API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )
    bitget_unified_perpetual_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Bitget Unified Perpetual secret key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )
    bitget_unified_perpetual_passphrase: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Bitget Unified Perpetual passphrase",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )
    model_config = ConfigDict(title="bitget_unified_perpetual")


KEYS = BitgetUnifiedPerpetualConfigMap.model_construct()
