from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "grvt_perpetual"

TESTNET_DOMAIN = "grvt_perpetual_testnet"

DOMAIN_TO_ENV = {
    DEFAULT_DOMAIN: "prod",
    TESTNET_DOMAIN: "testnet",
}

DOMAIN_TO_BASE_URLS = {
    DEFAULT_DOMAIN: {
        "edge": "https://edge.grvt.io",
        "trade": "https://trades.grvt.io",
        "market": "https://market-data.grvt.io",
        "trade_ws": "wss://trades.grvt.io/ws/full",
        "market_ws": "wss://market-data.grvt.io/ws/full",
    },
    TESTNET_DOMAIN: {
        "edge": "https://edge.testnet.grvt.io",
        "trade": "https://trades.testnet.grvt.io",
        "market": "https://market-data.testnet.grvt.io",
        "trade_ws": "wss://trades.testnet.grvt.io/ws/full",
        "market_ws": "wss://market-data.testnet.grvt.io/ws/full",
    },
}

HBOT_BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = 20  # uint64 decimal string
CLIENT_ORDER_ID_HIGH_BIT = 1 << 63
PRICE_SCALE = 1_000_000_000
WS_HEARTBEAT_TIME_INTERVAL = 30
FUNDING_RATE_UPDATE_INTERVAL = 8 * 60 * 60
COOKIE_REFRESH_INTERVAL_BUFFER = 5
ORDER_SIGNATURE_EXPIRATION_SECS = 24 * 60 * 60

AUTH_PATH_URL = "auth/api_key/login"

CREATE_ORDER_PATH_URL = "full/v1/create_order"
CANCEL_ORDER_PATH_URL = "full/v1/cancel_order"
OPEN_ORDERS_PATH_URL = "full/v1/open_orders"
ORDER_PATH_URL = "full/v1/order"
ORDER_HISTORY_PATH_URL = "full/v1/order_history"
FILL_HISTORY_PATH_URL = "full/v1/fill_history"
POSITIONS_PATH_URL = "full/v1/positions"
ACCOUNT_SUMMARY_PATH_URL = "full/v1/account_summary"
FUNDING_PAYMENT_HISTORY_PATH_URL = "full/v1/funding_payment_history"
GET_ALL_INITIAL_LEVERAGE_PATH_URL = "full/v1/get_all_initial_leverage"
SET_INITIAL_LEVERAGE_PATH_URL = "full/v1/set_initial_leverage"

INSTRUMENTS_PATH_URL = "full/v1/instruments"
ALL_INSTRUMENTS_PATH_URL = "full/v1/all_instruments"
INSTRUMENT_PATH_URL = "full/v1/instrument"
TICKER_PATH_URL = "full/v1/ticker"
MINI_TICKER_PATH_URL = "full/v1/mini"
ORDER_BOOK_PATH_URL = "full/v1/book"
TRADES_PATH_URL = "full/v1/trade"
TRADE_HISTORY_PATH_URL = "full/v1/trade_history"
FUNDING_PATH_URL = "full/v1/funding"
KLINE_PATH_URL = "full/v1/kline"
TIME_PATH_URL = "time"

PUBLIC_WS_CHANNEL_TRADE = "v1.trade"
PUBLIC_WS_CHANNEL_BOOK_SNAPSHOT = "v1.book.s"
PUBLIC_WS_CHANNEL_BOOK_DIFF = "v1.book.d"
PUBLIC_WS_CHANNEL_TICKER = "v1.ticker.s"
PUBLIC_WS_CHANNEL_CANDLE = "v1.candle"
PRIVATE_WS_CHANNEL_ORDER = "v1.order"
PRIVATE_WS_CHANNEL_STATE = "v1.state"
PRIVATE_WS_CHANNEL_POSITION = "v1.position"
PRIVATE_WS_CHANNEL_FILL = "v1.fill"

ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "OPEN": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "REJECTED": OrderState.FAILED,
    "CANCELLED": OrderState.CANCELED,
}

ORDER_NOT_FOUND_MESSAGE = "RESOURCE_NOT_FOUND"

TIME_IN_FORCE_GOOD_TILL_TIME = "GOOD_TILL_TIME"
TIME_IN_FORCE_IMMEDIATE_OR_CANCEL = "IMMEDIATE_OR_CANCEL"
TIME_IN_FORCE_FILL_OR_KILL = "FILL_OR_KILL"

GLOBAL_RATE_LIMIT_ID = "grvtGlobalRateLimit"
RATE_LIMITS = [
    RateLimit(limit_id=GLOBAL_RATE_LIMIT_ID, limit=1200, time_interval=60),
]

for limit_id in [
    AUTH_PATH_URL,
    CREATE_ORDER_PATH_URL,
    CANCEL_ORDER_PATH_URL,
    OPEN_ORDERS_PATH_URL,
    ORDER_PATH_URL,
    ORDER_HISTORY_PATH_URL,
    FILL_HISTORY_PATH_URL,
    POSITIONS_PATH_URL,
    ACCOUNT_SUMMARY_PATH_URL,
    FUNDING_PAYMENT_HISTORY_PATH_URL,
    GET_ALL_INITIAL_LEVERAGE_PATH_URL,
    SET_INITIAL_LEVERAGE_PATH_URL,
    INSTRUMENTS_PATH_URL,
    ALL_INSTRUMENTS_PATH_URL,
    INSTRUMENT_PATH_URL,
    TICKER_PATH_URL,
    MINI_TICKER_PATH_URL,
    ORDER_BOOK_PATH_URL,
    TRADES_PATH_URL,
    TRADE_HISTORY_PATH_URL,
    FUNDING_PATH_URL,
    KLINE_PATH_URL,
    TIME_PATH_URL,
]:
    RATE_LIMITS.append(
        RateLimit(
            limit_id=limit_id,
            limit=1200,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_RATE_LIMIT_ID)],
        )
    )
