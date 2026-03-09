from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "bluefin_perpetual"
MAX_ORDER_ID_LEN = None

# Domains
DOMAIN = EXCHANGE_NAME
STAGING_DOMAIN = "bluefin_perpetual_staging"

# Environment names used in SDK
MAINNET_ENV_NAME = "sui-prod"
STAGING_ENV_NAME = "sui-staging"

# Base URLs - constructed from environment name
# For mainnet (sui-prod):
#   Auth: https://auth.api.sui-prod.bluefin.io
#   API: https://api.sui-prod.bluefin.io
#   Trade: https://trade.api.sui-prod.bluefin.io
#   Account WS: wss://stream.api.sui-prod.bluefin.io/ws/account
#   Market WS: wss://stream.api.sui-prod.bluefin.io/ws/market
# For staging (sui-staging):
#   Auth: https://auth.api.sui-staging.bluefin.io
#   API: https://api.sui-staging.bluefin.io
#   Trade: https://trade.api.sui-staging.bluefin.io
#   Account WS: wss://stream.api.sui-staging.bluefin.io/ws/account
#   Market WS: wss://stream.api.sui-staging.bluefin.io/ws/market

def get_rest_url_for_env(env_name: str, service: str = "api") -> str:
    """Get REST base URL for a given environment and service."""
    return f"https://{service}.api.{env_name}.bluefin.io"

def get_ws_url_for_env(env_name: str, stream_type: str = "market") -> str:
    """Get WebSocket URL for a given environment and stream type."""
    return f"wss://stream.api.{env_name}.bluefin.io/ws/{stream_type}"

# Funding rate update interval
FUNDING_RATE_UPDATE_INTERVAL_SECOND = 3600  # Hourly

# Collateral currency
CURRENCY = "USDC"

# Order state mapping from Bluefin OrderStatus to Hummingbot OrderState
ORDER_STATE = {
    "STANDBY": OrderState.OPEN,
    "OPEN": OrderState.OPEN,
    "PARTIALLY_FILLED_OPEN": OrderState.PARTIALLY_FILLED,
    "PARTIALLY_FILLED_CANCELED": OrderState.CANCELED,
    "FILLED": OrderState.FILLED,
    "CANCELLED": OrderState.CANCELED,
    "EXPIRED": OrderState.CANCELED,
    "PARTIALLY_FILLED_EXPIRED": OrderState.CANCELED,
    "UNSPECIFIED": OrderState.FAILED,
}

# Heartbeat
HEARTBEAT_TIME_INTERVAL = 30.0

# Rate Limits
# Based on typical exchange limits - conservative estimate
MAX_REQUEST = 1200
ALL_ENDPOINTS_LIMIT = "All"

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=MAX_REQUEST, time_interval=60),
]
