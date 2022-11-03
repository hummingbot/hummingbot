from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

EXCHANGE_NAME = "gate_io_perpetual"
DEFAULT_DOMAIN = ""
HBOT_BROKER_ID = "hummingbot"
HBOT_ORDER_ID = "t-HBOT"
MAX_ID_LEN = 30

REST_URL = "https://api.gateio.ws/api/v4"
REST_URL_AUTH = "/api/v4"
WS_URL = "wss://fx-ws.gateio.ws/v4/ws/usdt"

# Public API v4 Endpoints
EXCHANGE_INFO_URL = "futures/usdt/contracts"
TICKER_PATH_URL = "futures/usdt/tickers"
ORDER_BOOK_PATH_URL = "futures/usdt/order_book"
MY_TRADES_PATH_URL = "futures/usdt/my_trades"
MARK_PRICE_URL = "futures/usdt/contracts/{id}"
NETWORK_CHECK_PATH_URL = "futures/usdt/contracts/BTC_USDT"
FUNDING_RATE_TIME_PATH_URL = "futures/usdt/funding_rate"

ORDER_CREATE_PATH_URL = "futures/usdt/orders"
ORDER_DELETE_PATH_URL = "futures/usdt/orders/{id}"
USER_BALANCES_PATH_URL = "futures/usdt/accounts"
POSITION_INFORMATION_URL = "futures/usdt/positions"
ORDER_STATUS_PATH_URL = "futures/usdt/orders/{id}"
USER_ORDERS_PATH_URL = "futures/usdt/orders"
SET_POSITION_MODE_URL = "futures/usdt/dual_mode"
ONEWAY_SET_LEVERAGE_PATH_URL = "futures/usdt/positions/{contract}/leverage"
HEDGE_SET_LEVERAGE_PATH_URL = "futures/usdt/dual_comp/positions/{contract}/leverage"

TICKER_ENDPOINT_NAME = "futures.tickers"
TRADES_ENDPOINT_NAME = "futures.trades"
ORDER_SNAPSHOT_ENDPOINT_NAME = "futures.order_book"
ORDERS_UPDATE_ENDPOINT_NAME = "futures.order_book_update"
USER_TRADES_ENDPOINT_NAME = "futures.usertrades"
USER_ORDERS_ENDPOINT_NAME = "futures.orders"
USER_BALANCE_ENDPOINT_NAME = "futures.balances"
USER_POSITIONS_ENDPOINT_NAME = "futures.positions"
PONG_CHANNEL_NAME = "futures.pong"

# Timeouts
MESSAGE_TIMEOUT = 30.0
PING_TIMEOUT = 10.0
API_CALL_TIMEOUT = 10.0
API_MAX_RETRIES = 4

# Funding Settlement Time Span
FUNDING_SETTLEMENT_DURATION = (0, 30)  # seconds before snapshot, seconds after snapshot

# Intervals
# Only used when nothing is received from WS
SHORT_POLL_INTERVAL = 5.0
# 45 seconds should be fine since we get trades, orders and balances via WS
LONG_POLL_INTERVAL = 45.0
# One minute should be fine since we get trades, orders and balances via WS
UPDATE_ORDER_STATUS_INTERVAL = 60.0
# 10 minute interval to update trading rules, these would likely never change whilst running.
INTERVAL_TRADING_RULES = 600

PUBLIC_URL_POINTS_LIMIT_ID = "PublicPoints"
PRIVATE_URL_POINTS_LIMIT_ID = "PrivatePoints"  # includes place-orders
CANCEL_ORDERS_LIMITS_ID = "CancelOrders"
ORDER_DELETE_LIMIT_ID = "OrderDelete"
ORDER_STATUS_LIMIT_ID = "OrderStatus"
RATE_LIMITS = [
    RateLimit(limit_id=PUBLIC_URL_POINTS_LIMIT_ID, limit=300, time_interval=1),
    RateLimit(limit_id=PRIVATE_URL_POINTS_LIMIT_ID, limit=400, time_interval=1),
    RateLimit(limit_id=CANCEL_ORDERS_LIMITS_ID, limit=400, time_interval=1),
    RateLimit(limit_id=NETWORK_CHECK_PATH_URL, limit=300, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=EXCHANGE_INFO_URL, limit=300, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=ORDER_CREATE_PATH_URL, limit=100, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=ORDER_DELETE_LIMIT_ID, limit=400, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(CANCEL_ORDERS_LIMITS_ID)]),
    RateLimit(limit_id=USER_BALANCES_PATH_URL, limit=400, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=SET_POSITION_MODE_URL, limit=400, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=POSITION_INFORMATION_URL, limit=400, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=ORDER_STATUS_LIMIT_ID, limit=400, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=ONEWAY_SET_LEVERAGE_PATH_URL, limit=400, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=HEDGE_SET_LEVERAGE_PATH_URL, limit=400, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=USER_ORDERS_PATH_URL, limit=400, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=TICKER_PATH_URL, limit=300, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=MARK_PRICE_URL, limit=300, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=FUNDING_RATE_TIME_PATH_URL, limit=300, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=ORDER_BOOK_PATH_URL, limit=300, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=MY_TRADES_PATH_URL, limit=400, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_URL_POINTS_LIMIT_ID)]),
]
