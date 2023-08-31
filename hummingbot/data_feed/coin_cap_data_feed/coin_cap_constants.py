import sys

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

UNIVERSAL_QUOTE_TOKEN = "USD"  # coincap only works with USD

BASE_REST_URL = "https://api.coincap.io/v2"
BASE_WS_URL = "wss://ws.coincap.io/prices?assets="

ALL_ASSETS_ENDPOINT = "/assets"
ASSET_ENDPOINT = "/assets/{}"
HEALTH_CHECK_ENDPOINT = ASSET_ENDPOINT.format("bitcoin")  # get a single asset

ALL_ASSETS_LIMIT_ID = "allAssetsLimitID"
ASSET_LIMIT_ID = "assetLimitID"
NO_KEY_LIMIT_ID = "noKeyLimitID"
API_KEY_LIMIT_ID = "APIKeyLimitID"
WS_CONNECTIONS_LIMIT_ID = "WSConnectionsLimitID"
NO_KEY_LIMIT = 200
API_KEY_LIMIT = 500
NO_LIMIT = sys.maxsize
MINUTE = 60
SECOND = 1

RATE_LIMITS = [
    RateLimit(limit_id=API_KEY_LIMIT_ID, limit=API_KEY_LIMIT, time_interval=MINUTE),
    RateLimit(
        limit_id=NO_KEY_LIMIT_ID,
        limit=NO_KEY_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(API_KEY_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=WS_CONNECTIONS_LIMIT_ID,
        limit=NO_LIMIT,
        time_interval=SECOND,
    ),
]
