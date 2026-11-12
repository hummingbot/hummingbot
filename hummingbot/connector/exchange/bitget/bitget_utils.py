from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.connector.exchange.bitget import bitget_constants as CONSTANTS
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Bitget fees: https://www.bitget.com/en/rate?tab=1

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
    buy_percent_fee_deducted_from_returns=True,
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return bool(exchange_info.get("symbol"))


def is_instrument_tradable(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if new orders may be placed on a trading pair based on its exchange information.

    This is deliberately narrower than :func:`is_exchange_information_valid`, which stays
    permissive so that the symbol map keeps covering every instrument. A pair that is suspended
    while the account still holds orders on it must remain resolvable, or order and fill updates
    referencing it can no longer be translated back to a trading pair.

    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair accepts new orders, False otherwise
    """
    # V3 instruments reports the listing state in "status"; only an online instrument accepts
    # orders. Withholding the trading rule is what stops orders being placed, since the connector
    # refuses to create an order for a pair that has no rule.
    online = exchange_info.get("status") == CONSTANTS.INSTRUMENT_STATUS_ONLINE

    return is_exchange_information_valid(exchange_info) and online


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


KEYS = BitgetConfigMap.model_construct()
