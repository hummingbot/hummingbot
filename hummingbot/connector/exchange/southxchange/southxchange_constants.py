# A single source of truth for constant variables related to the exchange
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "southxchange"
REST_URL = "https://www.southxchange.com/api/v4/"
WS_URL = "wss://www.southxchange.com/api/v4/connect"
PUBLIC_WS_URL = WS_URL
PRIVATE_WS_URL = WS_URL + '?token={access_token}'

SIDE_BUY = 'BUY'
SIDE_SELL = 'SELL'
PING_PATH_URL = "markets"

HBOT_BROKER_ID = "SX-HMBot"

DEFAULT_DOMAIN = "com"

ALL_ENDPOINTS_LIMIT = "All"
RATE_LIMITS = [
    RateLimit(limit_id="SXC", limit=239, time_interval=60, linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
]

ORDER_STATE = {
    "pending": OrderState.PENDING_CREATE,
    "booked": OrderState.OPEN,
    "executed": OrderState.FILLED,
    "partiallyexecuted": OrderState.PARTIALLY_FILLED,
    "canceledpartiallyexecuted": OrderState.CANCELED,
    "cancelednotexecuted": OrderState.CANCELED,
    "notenoughbalance": OrderState.FAILED,
    "amountbelowminimum": OrderState.FAILED,
    "partiallyexecutedbutnotenoughbalance": OrderState.FAILED,
}
