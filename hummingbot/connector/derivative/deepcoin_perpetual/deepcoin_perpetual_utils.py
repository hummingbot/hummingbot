from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PositionSide, TradeType
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Deepcoin fees
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0004"),
    taker_percent_fee_decimal=Decimal("0.0006"),
)

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    """
    return (exchange_info.get("instType") == "SWAP"
            and exchange_info.get("state") == "live")


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    """
    Converts exchange trading pair to Hummingbot format
    """
    if exchange_trading_pair:
        pair = exchange_trading_pair.replace("-SWAP", "")
        return pair
    return None


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    """
    Converts Hummingbot trading pair to exchange format
    """
    return hb_trading_pair + ("-SWAP")


def is_exchange_inverse(hb_trading_pair: str) -> bool:
    """
    Converts Hummingbot trading pair to exchange format
    """
    _, quote_asset = split_hb_trading_pair(hb_trading_pair)
    if quote_asset == "USD":
        return True
    return False


def convert_from_exchange_order_type(exchange_order_type: str) -> OrderType:
    """
    Converts exchange order type to Hummingbot OrderType
    """
    if exchange_order_type.upper() == "LIMIT":
        return OrderType.LIMIT
    elif exchange_order_type.upper() == "MARKET":
        return OrderType.MARKET
    elif exchange_order_type.upper() == "POST_ONLY":
        return OrderType.LIMIT_MAKER
    else:
        return OrderType.LIMIT


def convert_to_exchange_order_type(order_type: OrderType) -> str:
    """
    Converts Hummingbot OrderType to exchange order type
    """
    if order_type == OrderType.LIMIT:
        return "limit"
    elif order_type == OrderType.MARKET:
        return "market"
    elif order_type == OrderType.LIMIT_MAKER:
        return "post_only"
    else:
        return "limit"


def convert_from_exchange_side(exchange_side: str) -> TradeType:
    """
    Converts exchange side to Hummingbot TradeType
    """
    if exchange_side.upper() == "BUY":
        return TradeType.BUY
    elif exchange_side.upper() == "SELL":
        return TradeType.SELL
    else:
        return TradeType.BUY


def convert_to_exchange_side(trade_type: TradeType) -> str:
    """
    Converts Hummingbot TradeType to exchange side
    """
    if trade_type == TradeType.BUY:
        return "buy"
    elif trade_type == TradeType.SELL:
        return "sell"
    else:
        return "buy"


def convert_from_exchange_position_side(exchange_position_side: str) -> PositionSide:
    """
    Converts exchange position side to Hummingbot PositionSide
    """
    if exchange_position_side.lower() == "long":
        return PositionSide.LONG
    elif exchange_position_side.lower() == "short":
        return PositionSide.SHORT
    else:
        return PositionSide.LONG


class DeepcoinPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "deepcoin_perpetual"
    deepcoin_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Deepcoin Perpetual API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    deepcoin_perpetual_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Deepcoin Perpetual API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    deepcoin_perpetual_passphrase: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Deepcoin Perpetual API passphrase",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    model_config = ConfigDict(title="deepcoin_perpetual")


KEYS = DeepcoinPerpetualConfigMap.model_construct()


class DeepcoinPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "deepcoin_perpetual_testnet"
    deepcoin_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Deepcoin Perpetual Testnet API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    deepcoin_perpetual_testnet_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Deepcoin Perpetual Testnet API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    deepcoin_perpetual_testnet_passphrase: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Deepcoin Perpetual Testnet API passphrase",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    model_config = ConfigDict(title="deepcoin_perpetual_testnet")


OTHER_DOMAINS_KEYS = {
    "deepcoin_perpetual_testnet": DeepcoinPerpetualTestnetConfigMap.model_construct()
}
