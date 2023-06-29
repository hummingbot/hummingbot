import sys

from hummingbot.core.api_throttler.data_types import RateLimit

EXCHANGE_NAME = "injective"

DEFAULT_DOMAIN = ""
TESTNET_DOMAIN = "testnet"


ORDERBOOK_LIMIT_ID = "OrderBookSnapshot"


NO_LIMIT = sys.maxsize
ONE_SECOND = 1

RATE_LIMITS = [
    RateLimit(limit_id=ORDERBOOK_LIMIT_ID, limit=NO_LIMIT, time_interval=ONE_SECOND),
]
