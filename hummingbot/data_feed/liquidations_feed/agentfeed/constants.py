from hummingbot.core.api_throttler.data_types import RateLimit

# AgentFeed (https://x402.ochinimus.app) serves cross-venue liquidation pressure, computed by AgentFeed, in 5-second buckets.
# The route is paid: $0.001 per call, $0.0005 per call with a prepaid key (https://x402.ochinimus.app/keys).
REST_URL = "https://x402.ochinimus.app"
LIQUIDATIONS_ENDPOINT = "/api/liq-feed"
HEALTH_CHECK_ENDPOINT = "/api/sample"  # free, needs no key

API_KEY_HEADER = "X-AgentFeed-Key"
API_KEY_ENV_VAR = "AGENTFEED_API_KEY"

BUCKET_SECONDS = 5
SETTLE_SECONDS = 10  # the route serves a bucket only once it is this old, so late prints still land in it
RETENTION_SLACK_SECONDS = 5
MAX_SYMBOLS = 20  # the route takes at most 20 symbols per call
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]  # what the route serves when asked for none

# The server allows one call per 10 seconds per key (more only while an answer says has_more).
DEFAULT_POLL_INTERVAL_SECONDS = 30.0
MIN_POLL_INTERVAL_SECONDS = 10.0
AUTH_RETRY_SECONDS = 300.0  # after a 401/402 the key may be topped up: look again slowly, without log spam
MAX_BACKOFF_SECONDS = 300.0
SEEN_BUCKETS_LIMIT = 5000

RATE_LIMITS = [
    RateLimit(limit_id=LIQUIDATIONS_ENDPOINT, limit=6, time_interval=60),
    RateLimit(limit_id=HEALTH_CHECK_ENDPOINT, limit=30, time_interval=60),
]
