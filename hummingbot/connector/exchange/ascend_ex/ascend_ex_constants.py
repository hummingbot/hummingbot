# A single source of truth for constant variables related to the exchange
from typing import Dict
from hummingbot.core.api_throttler.data_types import RateLimit

EXCHANGE_NAME = "ascend_ex"
REST_URL = "https://ascendex.com/api/pro/v1"
WS_URL = "wss://ascendex.com/0/api/pro/v1/stream"
PONG_PAYLOAD = {"op": "pong"}

# REST API ENDPOINTS
ORDER_PATH_URL = "cash/order"
ORDER_BATCH_PATH_URL = "cash/order/batch"
ORDER_OPEN_PATH_URL = "cash/order/open"
ORDER_STATUS_PATH_URL = "cash/order/status"
BALANCE_PATH_URL = "cash/balance"
HIST_PATH_URL = "order/hist"
TICKER_PATH_URL = "ticker"
PRODUCTS_PATH_URL = "products"

# AscendEx has multiple pools for API request limits
# Any call increases call rate in ALL pool, so e.g. a cash/order call will contribute to both ALL and cash/order pools.
ALL_ENDPOINTS_LIMIT = "All"
RATE_LIMITS = [
    RateLimit(limit_id=ALL_ENDPOINTS_LIMIT, limit=100, time_interval=1),
    RateLimit(limit_id=ORDER_PATH_URL, limit=50, time_interval=1, linked_limits=[ALL_ENDPOINTS_LIMIT]),
    RateLimit(limit_id=ORDER_BATCH_PATH_URL, limit=50, time_interval=1, linked_limits=[ALL_ENDPOINTS_LIMIT]),
    RateLimit(limit_id=ORDER_OPEN_PATH_URL, limit=50, time_interval=1, linked_limits=[ALL_ENDPOINTS_LIMIT]),
    RateLimit(limit_id=ORDER_STATUS_PATH_URL, limit=50, time_interval=1, linked_limits=[ALL_ENDPOINTS_LIMIT]),
    RateLimit(limit_id=BALANCE_PATH_URL, limit=100, time_interval=1, linked_limits=[ALL_ENDPOINTS_LIMIT]),
    RateLimit(limit_id=HIST_PATH_URL, limit=60, time_interval=60, linked_limits=[ALL_ENDPOINTS_LIMIT]),
    RateLimit(limit_id=TICKER_PATH_URL, limit=100, time_interval=1, linked_limits=[ALL_ENDPOINTS_LIMIT]),
    RateLimit(limit_id=PRODUCTS_PATH_URL, limit=100, time_interval=1, linked_limits=[ALL_ENDPOINTS_LIMIT]),
]
