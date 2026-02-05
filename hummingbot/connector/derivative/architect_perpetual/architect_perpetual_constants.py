from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "architect_perpetual"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = 36

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "architect_perpetual_testnet"

# API URLs
PERPETUAL_BASE_URL = "https://gateway.architect.exchange/api"
TESTNET_BASE_URL = "https://gateway.sandbox.architect.exchange/api"

# WebSocket URLs
PERPETUAL_WS_URL = "wss://gateway.architect.exchange/api/marketdata"
PERPETUAL_ORDERS_WS_URL = "wss://gateway.architect.exchange/api/orders"
TESTNET_WS_URL = "wss://gateway.sandbox.architect.exchange/api/marketdata"
TESTNET_ORDERS_WS_URL = "wss://gateway.sandbox.architect.exchange/api/orders"

FUNDING_RATE_UPDATE_INTERVAL_SECOND = 60
HEARTBEAT_TIME_INTERVAL = 30.0

CURRENCY = "USD"

# REST Endpoints
WHOAMI_URL = "/whoami"
AUTHENTICATE_URL = "/authenticate"
TICKERS_URL = "/tickers"
TICKER_URL = "/ticker"
INSTRUMENTS_URL = "/instruments"
INSTRUMENT_URL = "/instrument"
BALANCES_URL = "/balances"
POSITIONS_URL = "/positions"
OPEN_ORDERS_URL = "/open_orders"
PLACE_ORDER_URL = "/place_order"
CANCEL_ORDER_URL = "/cancel_order"
FILLS_URL = "/fills"
FUNDING_RATES_URL = "/funding-rates"
CANDLES_URL = "/candles"
RISK_SNAPSHOT_URL = "/risk-snapshot"

# Order States
ORDER_STATE = {
    "open": OrderState.OPEN,
    "pending": OrderState.PENDING_CREATE,
    "filled": OrderState.FILLED,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "cancelled": OrderState.CANCELED,
    "canceled": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
    "expired": OrderState.CANCELED,
}

# Rate Limits
MAX_REQUEST = 100
ALL_ENDPOINTS_LIMIT = "All"

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=MAX_REQUEST, time_interval=60),
    RateLimit(limit_id=TICKERS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=INSTRUMENTS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=BALANCES_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=POSITIONS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=OPEN_ORDERS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=PLACE_ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=CANCEL_ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=FILLS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=FUNDING_RATES_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
]

ORDER_NOT_EXIST_MESSAGE = "order not found"
UNKNOWN_ORDER_MESSAGE = "Order was never placed, already canceled, or filled"
