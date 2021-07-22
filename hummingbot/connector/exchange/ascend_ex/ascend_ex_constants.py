# A single source of truth for constant variables related to the exchange
from typing import Dict
from hummingbot.core.api_throttler.data_types import CallRateLimit

EXCHANGE_NAME = "ascend_ex"
REST_URL = "https://ascendex.com/api/pro/v1"
WS_URL = "wss://ascendex.com/0/api/pro/v1/stream"
PONG_PAYLOAD = {"op": "pong"}

# AscendEx has multiple pools for API request limits
# Any call increases call rate in ALL pool, so e.g. a cash/order call will contribute to both ALL and cash/order pools.
REQUEST_CALL_LIMITS: Dict[str, CallRateLimit] = {
    "all_endpoints": CallRateLimit(limit_id="all_endpoints", limit=100, time_interval=1),
    "cash/order": CallRateLimit(limit_id="cash/order", limit=50, time_interval=1),
    "order/hist": CallRateLimit(limit_id="order/hist", limit=60, time_interval=60)
}
