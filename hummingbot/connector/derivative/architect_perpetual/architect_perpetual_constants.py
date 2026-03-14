from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "architect_perpetual"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = None
MIN_NOTIONAL_SIZE = 1.0

DOMAIN = EXCHANGE_NAME
PAPER_DOMAIN = "architect_perpetual_paper"

# Architect gRPC endpoint
GRPC_ENDPOINT = "app.architect.co"
PAPER_GRPC_ENDPOINT = "app.architect.co"  # Same endpoint, paper_trading=True flag

# Default execution venue for perpetual futures
DEFAULT_EXECUTION_VENUE = "BINANCE"

# Symbol suffix for perpetual contracts on Architect
# Format: "{BASE}-{QUOTE} {VENUE} Perpetual"
PERPETUAL_SYMBOL_SUFFIX = "Perpetual"

# Funding rate poll interval (seconds)
FUNDING_RATE_UPDATE_INTERVAL = 60
HEARTBEAT_TIME_INTERVAL = 30.0

# Rate limits (Architect: 100 burst, 10/sec refill)
MAX_REQUEST = 600  # 1-minute window equivalent
ALL_ENDPOINTS_LIMIT = "All"

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=MAX_REQUEST, time_interval=60),
    RateLimit(limit_id="place_order", limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id="cancel_order", limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id="get_order", limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id="get_positions", limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id="get_account_summary", limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id="list_symbols", limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
]

# Order state mapping from Architect OrderStatus → Hummingbot OrderState
ORDER_STATE = {
    "Pending": OrderState.PENDING_CREATE,
    "Open": OrderState.OPEN,
    "Rejected": OrderState.FAILED,
    "Out": OrderState.FILLED,
    "Canceling": OrderState.OPEN,
    "Canceled": OrderState.CANCELED,
    "ReconciledOut": OrderState.FILLED,
    "ModifiedOut": OrderState.OPEN,
    "Stale": OrderState.FAILED,
    "Unknown": OrderState.OPEN,
}

ORDER_NOT_EXIST_MESSAGE = "order not found"
