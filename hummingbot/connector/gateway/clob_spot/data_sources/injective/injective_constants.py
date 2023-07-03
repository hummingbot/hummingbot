from decimal import Decimal
from typing import Dict, Tuple

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState

NONCE_PATH = "injective/exchange/v1beta1/exchange"

CONNECTOR_NAME = "injective"
REQUESTS_SKIP_STEP = 100
LOST_ORDER_COUNT_LIMIT = 10
ORDER_CHAIN_PROCESSING_TIMEOUT = 5
MARKETS_UPDATE_INTERVAL = 8 * 60 * 60
DEFAULT_SUB_ACCOUNT_SUFFIX = "000000000000000000000000"
CLIENT_TO_BACKEND_ORDER_TYPES_MAP: Dict[Tuple[TradeType, OrderType], str] = {
    (TradeType.BUY, OrderType.LIMIT): "buy",
    (TradeType.BUY, OrderType.LIMIT_MAKER): "buy_po",
    (TradeType.BUY, OrderType.MARKET): "take_buy",
    (TradeType.SELL, OrderType.LIMIT): "sell",
    (TradeType.SELL, OrderType.LIMIT_MAKER): "sell_po",
    (TradeType.SELL, OrderType.MARKET): "take_sell",
}

BACKEND_TO_CLIENT_ORDER_STATE_MAP = {
    "booked": OrderState.OPEN,
    "partial_filled": OrderState.PARTIALLY_FILLED,
    "filled": OrderState.FILLED,
    "canceled": OrderState.CANCELED,
}

INJ_TOKEN_DENOM = "inj"
MIN_GAS_PRICE_IN_INJ = (
    5 * Decimal("1e8")  # https://api.injective.exchange/#faq-3-how-can-i-calculate-the-gas-fees-in-inj
)
BASE_GAS = Decimal("100e3")
GAS_BUFFER = Decimal("20e3")
SPOT_SUBMIT_ORDER_GAS = Decimal("45e3")
SPOT_CANCEL_ORDER_GAS = Decimal("25e3")

MSG_CREATE_SPOT_LIMIT_ORDER = "/injective.exchange.v1beta1.MsgCreateSpotLimitOrder"
MSG_CANCEL_SPOT_ORDER = "/injective.exchange.v1beta1.MsgCancelSpotOrder"
MSG_BATCH_UPDATE_ORDERS = "/injective.exchange.v1beta1.MsgBatchUpdateOrders"

ACC_NONCE_PATH_RATE_LIMIT_ID = "acc_nonce"
RATE_LIMITS = [RateLimit(limit_id=ACC_NONCE_PATH_RATE_LIMIT_ID, limit=100, time_interval=1)]
