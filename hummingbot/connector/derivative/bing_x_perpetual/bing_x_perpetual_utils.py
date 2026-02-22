import gzip
import io
import json
import time
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0005"),
    buy_percent_fee_deducted_from_returns=True
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a perpetual trading pair is enabled to operate with based on its exchange information.
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("status") == 1


def decompress_ws_message(message):
    """
    BingX WebSocket sends gzip-compressed frames. This function decompresses them.
    """
    if isinstance(message, bytes):
        compressed_data = gzip.GzipFile(fileobj=io.BytesIO(message), mode='rb')
        decompressed_data = compressed_data.read()
        utf8_data = decompressed_data.decode('utf-8')
        return json.loads(utf8_data)
    else:
        return message


def get_trading_pair_from_exchange_symbol(exchange_symbol: str) -> str:
    """
    Convert BingX exchange symbol to Hummingbot trading pair format.
    BingX perpetual uses dash separator: BTC-USDT -> BTC-USDT (same format).
    """
    return exchange_symbol


def get_exchange_symbol_from_trading_pair(trading_pair: str) -> str:
    """
    Convert Hummingbot trading pair to BingX exchange symbol format.
    BingX perpetual uses dash separator: BTC-USDT -> BTC-USDT (same format).
    """
    return trading_pair


def get_next_funding_time() -> float:
    """
    BingX perpetual funding is paid every 8 hours at 00:00, 08:00, 16:00 UTC.
    Returns the next funding timestamp in seconds.
    """
    now = time.time()
    current_hour = int(now // 3600)
    # Next funding hour is the next multiple of 8
    next_funding_hour = ((current_hour // 8) + 1) * 8
    return float(next_funding_hour * 3600)


class BingXPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "bing_x_perpetual"
    bing_x_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your BingX Perpetual API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    bing_x_perpetual_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your BingX Perpetual API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="bing_x_perpetual")


KEYS = BingXPerpetualConfigMap.model_construct()
