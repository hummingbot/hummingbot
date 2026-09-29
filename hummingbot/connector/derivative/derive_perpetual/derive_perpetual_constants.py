from hummingbot.connector.constants import MINUTE, SECOND
from hummingbot.connector.other.derive_common_utils import compute_domain_separator
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "derive_perpetual"
TESTNET_DOMAIN = "derive_perpetual_testnet"
BROKER_ID = "HBOT"

FUNDING_RATE_UPDATE_INTERNAL_SECOND = 60

# v3 slim tickers report `f` as the current *hourly* funding rate, and perp_details carries the
# hourly min/max bounds, so funding continues to settle hourly.
FUNDING_INTERVAL_SECONDS = 60 * 60

MAX_ORDER_ID_LEN = 32

REFERRAL_CODE = "0x27F53feC538e477CE3eA1a456027adeCAC919DfD"  # noqa: mock

# v3 settles on Ethereum L1 (mainnet) and Sepolia (testnet), not the Derive L2 chain 957.
CHAIN_ID = 1
TESTNET_CHAIN_ID = 11155111

# The Matching contract and the trade module are the same address on every network in v3.
MATCHING_CONTRACT_ADDRESS = "0xeB8d770ec18DB98Db922E9D83260A585b9F0DeAD"  # noqa: mock
TRADE_MODULE_ADDRESS = "0xB8D20c2B7a1Ad2EE33Bc50eF10876eD3035b5e7b"  # noqa: mock
ACTION_TYPEHASH = "0x4d7a9f27c403ff9c0f19bce61d76d82f9aa29f8d6d4b0c5474607d9770d1af17"  # noqa: mock

# Derived rather than hardcoded. The v2 separator went stale precisely because it was a literal,
# and the test suite pins these against the values published in docs.derive.xyz.
DOMAIN_SEPARATOR = compute_domain_separator(CHAIN_ID, MATCHING_CONTRACT_ADDRESS)
TESTNET_DOMAIN_SEPARATOR = compute_domain_separator(TESTNET_CHAIN_ID, MATCHING_CONTRACT_ADDRESS)

# How long a signed action stays valid. v3 requires 5 minutes to 120 days (error 11011) and no
# later than the session key's own expiry (error 14038).
SIGNATURE_VALIDITY_SEC = 60 * 60

MARKET_ORDER_SLIPPAGE = 0.05

# Base URL
BASE_URL = "https://api.derive.xyz/v3"
WSS_URL = "wss://api.derive.xyz/v3/ws"

TESTNET_BASE_URL = "https://testnet.api.derive.xyz/v3"
TESTNET_WSS_URL = "wss://testnet.api.derive.xyz/v3/ws"

# The v3 instrument_type this connector trades.
INSTRUMENT_TYPE = "perp"

# v3 rejects REST requests that arrive without a User-Agent.
USER_AGENT = "hummingbot"

# Public API endpoints
TICKER_PRICE_CHANGE_PATH_URL = "/public/get_ticker"
BULK_TICKERS_PATH_URL = "/public/get_tickers"
EXCHANGE_INFO_PATH_URL = "/public/get_all_currencies"
EXCHANGE_CURRENCIES_PATH_URL = "/public/get_all_instruments"
PING_PATH_URL = "/public/get_time"
FUNDING_RATE_HISTORY_PATH_URL = "/public/get_funding_rate_history"
RATE_LIMITS_PATH_URL = "/public/getRateLimits"
SESSION_KEY_WALLETS_PATH_URL = "/public/get_wallets_from_session_key"

# Private API endpoints
ACCOUNTS_PATH_URL = "/private/get_subaccount"
COLLATERALS_PATH_URL = "/private/get_collaterals"
MY_TRADES_PATH_URL = "/private/get_trade_history"
CREATE_ORDER_URL = "/private/order"
ORDER_DEBUG_URL = "/private/order_debug"
CANCEL_ORDER_URL = "/private/cancel"
ORDER_STATUS_PATH_URL = "/private/get_order"
POSITION_INFORMATION_URL = "/private/get_positions"
GET_LAST_FUNDING_RATE_PATH_URL = "/private/get_funding_history"

# v3 removed /private/get_orders; open and historical orders are separate calls now.
OPEN_ORDERS_PATH_URL = "/private/get_open_orders"
ORDER_HISTORY_PATH_URL = "/private/get_order_history"

WS_PING_REQUEST = "ping"

# v3 has no positions websocket channel, so positions are polled.
WS_ORDERS_CHANNEL = "{subaccount_id}.orders"
WS_TRADES_CHANNEL = "{subaccount_id}.trades"
WS_BALANCES_CHANNEL = "{subaccount_id}.balances"

WS_HEARTBEAT_TIME_INTERVAL = 10

WS_CONNECTIONS_RATE_LIMIT = "WS_CONNECTIONS"

# DerivePerpetual params

SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

TIME_IN_FORCE_GTC = "gtc"  # Good till cancelled
TIME_IN_FORCE_IOC = "ioc"  # Immediate or cancel
TIME_IN_FORCE_FOK = "fok"  # Fill or kill
TIME_IN_FORCE_POST_ONLY = "post_only"  # Maker only; rejected if it would cross

# Rate Limit Type
ORDERS_IP = "market_maker_non_matching"

TRADER_ACCOUNTS_TYPE = "trader"
MARKET_MAKER_ACCOUNTS_TYPE = "market_maker"

# Rate Limit time intervals
ONE_SECOND = 1

TRADER_MATCHING = 5
TRADER_NON_MATCHING = 5

MARKET_MAKER_MATCHING = 5
MARKET_MAKER_NON_MATCHING = 500

# Rate Limit

ENDPOINTS = {
    "limits": {
        "matching": [CANCEL_ORDER_URL, CREATE_ORDER_URL],
        "non_matching": [
            ACCOUNTS_PATH_URL,
            COLLATERALS_PATH_URL,
            EXCHANGE_CURRENCIES_PATH_URL,
            EXCHANGE_INFO_PATH_URL,
            GET_LAST_FUNDING_RATE_PATH_URL,
            FUNDING_RATE_HISTORY_PATH_URL,
            MY_TRADES_PATH_URL,
            OPEN_ORDERS_PATH_URL,
            ORDER_HISTORY_PATH_URL,
            ORDER_STATUS_PATH_URL,
            PING_PATH_URL,
            POSITION_INFORMATION_URL,
            BULK_TICKERS_PATH_URL,
            TICKER_PRICE_CHANGE_PATH_URL
        ],
    },
}


# Order States. v3 adds expired, untriggered and algo_active.
ORDER_STATE = {
    "open": OrderState.OPEN,
    "untriggered": OrderState.OPEN,
    "algo_active": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "cancelled": OrderState.CANCELED,
    "expired": OrderState.FAILED,
    "rejected": OrderState.FAILED,
}

# Websocket event types
DIFF_EVENT_TYPE = "depthUpdate"
SNAPSHOT_EVENT_TYPE = "depthUpdate"
TRADE_EVENT_TYPE = "trade"
FUNDING_INFO_STREAM_ID = "ticker"

USER_ORDERS_ENDPOINT_NAME = "orders"
USEREVENT_ENDPOINT_NAME = "trades"

# v3 JSON-RPC error codes (docs.derive.xyz/error-codes). Matching on these replaces the string
# matching and the Binance-style codes the connector used to carry.
ERR_ORDER_DOES_NOT_EXIST = 11006
ERR_SELF_CROSSING = 11007
ERR_POST_ONLY_WOULD_CROSS = 11008
ERR_INSUFFICIENT_FUNDS = 11000
ERR_INVALID_NONCE = 11017
ERR_NONCE_ALREADY_USED = 11018
ERR_MAX_FEE_TOO_LOW = 11023
ERR_REDUCE_ONLY_WRONG_DIRECTION = 11024
ERR_REDUCE_ONLY_WOULD_INCREASE = 11025
ERR_SIGNATURE_EXPIRY_OUT_OF_BOUNDS = 11011
ERR_SESSION_KEY_NOT_FOUND = 14026
ERR_SESSION_KEY_EXPIRED = 14030
ERR_SESSION_KEY_UNAUTHORIZED_SCOPE = 14031
ERR_SIGNATURE_EXPIRY_AFTER_SESSION_KEY = 14038
ERR_RATE_LIMIT = -32000

ORDER_NOT_EXIST_ERROR_CODES = {ERR_ORDER_DOES_NOT_EXIST}
# 9000-9002 are transient engine errors that are safe to retry.
RETRYABLE_ERROR_CODES = {9000, 9001, 9002, ERR_RATE_LIMIT}
SESSION_KEY_ERROR_CODES = {
    ERR_SESSION_KEY_NOT_FOUND,
    ERR_SESSION_KEY_EXPIRED,
    ERR_SESSION_KEY_UNAUTHORIZED_SCOPE,
    ERR_SIGNATURE_EXPIRY_AFTER_SESSION_KEY,
}
SESSION_KEY_ERROR_HINTS = {
    ERR_SESSION_KEY_NOT_FOUND: (
        "The session key is not registered against this wallet. Register it at derive.xyz with a "
        "trading scope (trade:orderbook:perp or trade:orderbook:all) plus off-chain account_info."
    ),
    ERR_SESSION_KEY_EXPIRED: "The session key has expired. Register a new one at derive.xyz.",
    ERR_SESSION_KEY_UNAUTHORIZED_SCOPE: (
        "The session key does not carry a scope that permits this action. Perpetual trading needs "
        "trade:orderbook:perp (5) or trade:orderbook:all (3)."
    ),
    ERR_SIGNATURE_EXPIRY_AFTER_SESSION_KEY: (
        "The signature expiry is later than the session key's own expiry. Register a longer-lived "
        "session key or lower SIGNATURE_VALIDITY_SEC."
    ),
}

# Cancel reasons that indicate the signed max_fee was below what the trade actually cost.
CANCEL_REASON_MAX_FEE_TOO_LOW = "signed_max_fee_too_low"

RATE_LIMITS = [
    # Pools - will be updated in exchange info initialization
    RateLimit(limit_id=TRADER_ACCOUNTS_TYPE, limit=TRADER_NON_MATCHING, time_interval=SECOND),
    RateLimit(limit_id=MARKET_MAKER_ACCOUNTS_TYPE, limit=MARKET_MAKER_NON_MATCHING, time_interval=SECOND),
    RateLimit(limit_id=ORDERS_IP, limit=TRADER_MATCHING, time_interval=SECOND),
    # Weighted Limits
    RateLimit(
        limit_id=WSS_URL,
        limit=MARKET_MAKER_NON_MATCHING,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(MARKET_MAKER_ACCOUNTS_TYPE)]
    ),
    RateLimit(
        limit_id=TICKER_PRICE_CHANGE_PATH_URL,
        limit=MARKET_MAKER_NON_MATCHING,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(MARKET_MAKER_ACCOUNTS_TYPE)]
    ),
    RateLimit(
        limit_id=BULK_TICKERS_PATH_URL,
        limit=MARKET_MAKER_NON_MATCHING,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(MARKET_MAKER_ACCOUNTS_TYPE)]
    ),
    RateLimit(
        limit_id=POSITION_INFORMATION_URL,
        limit=MARKET_MAKER_NON_MATCHING,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(MARKET_MAKER_ACCOUNTS_TYPE)]
    ),
    RateLimit(
        limit_id=GET_LAST_FUNDING_RATE_PATH_URL,
        limit=MARKET_MAKER_NON_MATCHING,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(MARKET_MAKER_ACCOUNTS_TYPE)]
    ),
    RateLimit(
        limit_id=FUNDING_RATE_HISTORY_PATH_URL,
        limit=MARKET_MAKER_NON_MATCHING,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(MARKET_MAKER_ACCOUNTS_TYPE)]
    ),
    RateLimit(
        limit_id=EXCHANGE_INFO_PATH_URL,
        limit=MARKET_MAKER_NON_MATCHING,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(MARKET_MAKER_ACCOUNTS_TYPE)]
    ),
    RateLimit(
        limit_id=EXCHANGE_CURRENCIES_PATH_URL,
        limit=MARKET_MAKER_NON_MATCHING,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(MARKET_MAKER_ACCOUNTS_TYPE)],
    ),
    RateLimit(
        limit_id=PING_PATH_URL,
        limit=MARKET_MAKER_NON_MATCHING,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(MARKET_MAKER_ACCOUNTS_TYPE)]
    ),
    RateLimit(
        limit_id=RATE_LIMITS_PATH_URL,
        limit=MARKET_MAKER_NON_MATCHING,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(MARKET_MAKER_ACCOUNTS_TYPE)]
    ),
    RateLimit(
        limit_id=SESSION_KEY_WALLETS_PATH_URL,
        limit=MARKET_MAKER_NON_MATCHING,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(MARKET_MAKER_ACCOUNTS_TYPE)]
    ),
    RateLimit(
        limit_id=ACCOUNTS_PATH_URL,
        limit=MARKET_MAKER_NON_MATCHING,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(MARKET_MAKER_ACCOUNTS_TYPE)],
    ),
    RateLimit(
        limit_id=COLLATERALS_PATH_URL,
        limit=MARKET_MAKER_NON_MATCHING,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(MARKET_MAKER_ACCOUNTS_TYPE)],
    ),
    RateLimit(
        limit_id=CREATE_ORDER_URL,
        limit=TRADER_MATCHING,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(ORDERS_IP)],
    ),
    RateLimit(
        limit_id=ORDER_DEBUG_URL,
        limit=MARKET_MAKER_NON_MATCHING,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(MARKET_MAKER_ACCOUNTS_TYPE)],
    ),
    RateLimit(
        limit_id=CANCEL_ORDER_URL,
        limit=TRADER_MATCHING,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(ORDERS_IP)],
    ),
    RateLimit(
        limit_id=ORDER_STATUS_PATH_URL,
        limit=MARKET_MAKER_NON_MATCHING,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(MARKET_MAKER_ACCOUNTS_TYPE)],
    ),
    RateLimit(
        limit_id=MY_TRADES_PATH_URL,
        limit=MARKET_MAKER_NON_MATCHING,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(MARKET_MAKER_ACCOUNTS_TYPE)],
    ),
    RateLimit(
        limit_id=OPEN_ORDERS_PATH_URL,
        limit=MARKET_MAKER_NON_MATCHING,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(MARKET_MAKER_ACCOUNTS_TYPE)],
    ),
    RateLimit(
        limit_id=ORDER_HISTORY_PATH_URL,
        limit=MARKET_MAKER_NON_MATCHING,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(MARKET_MAKER_ACCOUNTS_TYPE)],
    ),
    RateLimit(
        limit_id=WS_CONNECTIONS_RATE_LIMIT,
        limit=500,
        time_interval=SECOND,
    ),
]
