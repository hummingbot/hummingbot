from typing import Dict, Tuple

from hummingbot.core.data_type.common import OrderType, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState

CONNECTOR_NAME = "injective_perpetual"

MARKETS_UPDATE_INTERVAL = 8 * 60 * 60

SUPPORTED_ORDER_TYPES = [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]
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
    (TradeType.BUY, OrderType.LIMIT): "buy_po",
    (TradeType.BUY, OrderType.LIMIT_MAKER): "buy_po",
    (TradeType.BUY, OrderType.MARKET): "take_buy",
    (TradeType.SELL, OrderType.LIMIT): "sell_po",
    (TradeType.SELL, OrderType.LIMIT_MAKER): "sell_po",
    (TradeType.SELL, OrderType.MARKET): "take_sell",
}

FETCH_ORDER_HISTORY_LIMIT = 100
