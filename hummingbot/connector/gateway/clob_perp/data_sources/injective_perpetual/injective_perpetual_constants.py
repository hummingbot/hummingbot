from configparser import ConfigParser
from decimal import Decimal
from typing import Dict, Tuple

from pyinjective.constant import (
    Network,
    devnet_config as DEVNET_TOKEN_META_CONFIG,
    mainnet_config as MAINNET_TOKEN_META_CONFIG,
    testnet_config as TESTNET_TOKEN_META_CONFIG,
)

from hummingbot.core.data_type.common import OrderType, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState

CONNECTOR_NAME = "injective_perpetual"
LOST_ORDER_COUNT_LIMIT = 3
ORDER_CHAIN_PROCESSING_TIMEOUT = 5

DEFAULT_SUB_ACCOUNT_SUFFIX = "000000000000000000000000"

NETWORK_CONFIG = {
    "mainnet": Network.mainnet(node="k8s"),
    "testnet": Network.testnet(),
    "devnet": Network.devnet()
}

MARKETS_UPDATE_INTERVAL = 8 * 60 * 60

SUPPORTED_ORDER_TYPES = [OrderType.LIMIT, OrderType.LIMIT_MAKER]
SUPPORTED_POSITION_MODES = [PositionMode.ONEWAY]

MSG_CREATE_DERIVATIVE_LIMIT_ORDER = "/injective.exchange.v1beta1.MsgCreateDerivativeLimitOrder"
MSG_CANCEL_DERIVATIVE_ORDER = "/injective.exchange.v1beta1.MsgCancelDerivativeOrder"
MSG_BATCH_UPDATE_ORDERS = "/injective.exchange.v1beta1.MsgBatchUpdateOrders"

INJ_DERIVATIVE_TX_EVENT_TYPES = [
    MSG_CREATE_DERIVATIVE_LIMIT_ORDER,
    MSG_CANCEL_DERIVATIVE_ORDER,
    MSG_BATCH_UPDATE_ORDERS,
]

INJ_DERIVATIVE_ORDER_STATES = {
    "booked": OrderState.OPEN,
    "partial_filled": OrderState.PARTIALLY_FILLED,
    "filled": OrderState.FILLED,
    "canceled": OrderState.CANCELED,
}

CLIENT_TO_BACKEND_ORDER_TYPES_MAP: Dict[Tuple[TradeType, OrderType], str] = {
    (TradeType.BUY, OrderType.LIMIT): "buy",
    (TradeType.BUY, OrderType.LIMIT_MAKER): "buy_po",
    (TradeType.BUY, OrderType.MARKET): "take_buy",
    (TradeType.SELL, OrderType.LIMIT): "sell",
    (TradeType.SELL, OrderType.LIMIT_MAKER): "sell_po",
    (TradeType.SELL, OrderType.MARKET): "take_sell",
}

FETCH_ORDER_HISTORY_LIMIT = 100

BASE_GAS = Decimal("100e3")
GAS_BUFFER = Decimal("20e3")
DERIVATIVE_SUBMIT_ORDER_GAS = Decimal("45e3")
DERIVATIVE_CANCEL_ORDER_GAS = Decimal("25e3")


def _parse_network_config_to_denom_meta(config: ConfigParser):
    """
    Parses token's denom configuration from Injective SDK.
    i.e.
    {
        "inj": {
            "symbol": "INJ",
            "decimal": 18
        },
        "peggy0xdAC17F958D2ee523a2206206994597C13D831ec7": {
            "symbol": "USDT",
            "decimal": 6
        },
    }
    """
    return {
        entry["peggy_denom"]: {"symbol": entry.name, "decimal": entry["decimals"]}
        for entry in config.values() if "peggy_denom" in entry
    }


NETWORK_DENOM_TOKEN_META = {
    "mainnet": _parse_network_config_to_denom_meta(config=MAINNET_TOKEN_META_CONFIG),
    "testnet": _parse_network_config_to_denom_meta(config=TESTNET_TOKEN_META_CONFIG),
    "devnet": _parse_network_config_to_denom_meta(config=DEVNET_TOKEN_META_CONFIG)
}
