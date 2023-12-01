import sys

from hummingbot.core.api_throttler.data_types import RateLimit

EXCHANGE_NAME = "penumbra"

NO_LIMIT = sys.maxsize

RATE_LIMITS = [
    RateLimit(limit_id='/*', limit=NO_LIMIT, time_interval=1),
]
