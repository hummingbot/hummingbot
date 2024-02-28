from hummingbot.core.api_throttler.data_types import RateLimit, LinkedLimitWeightPair


# A single source of truth for constant variables related to the exchange
class Constants:
    EXCHANGE_NAME = "altmarkets"
    REST_URL = "https://www.pmeex.com/api/v2/peatio"
    WS_PRIVATE_URL = "wss://www.pmeex.com/api/v2/ranger/private"
    WS_PUBLIC_URL = "wss://www.pmeex.com/api/v2/ranger/public"

    HBOT_BROKER_ID = "HBOT"

    USER_AGENT = "HBOT_AMv2"

    ENDPOINT = {
        # Public Endpoints
        "NETWORK_CHECK": "public/timestamp",
        "TICKER": "public/markets/tickers",
        "TICKER_SINGLE": "public/markets/{trading_pair}/tickers",
        "SYMBOL": "public/markets",
        "ORDER_BOOK": "public/markets/{trading_pair}/depth",
        "ORDER_CREATE": "market/orders",
        "ORDER_DELETE": "market/orders/{id}/cancel",
        "ORDER_STATUS": "market/orders/{id}",
        "USER_ORDERS": "market/orders",
        "USER_BALANCES": "account/balances",
    }

    WS_SUB = {
        "TRADES": "{trading_pair}.trades",
        "ORDERS": "{trading_pair}.ob-inc",
        "USER_ORDERS_TRADES": ['balance', 'order', 'trade'],

    }

    WS_EVENT_SUBSCRIBE = "subscribe"
    WS_EVENT_UNSUBSCRIBE = "unsubscribe"

    WS_METHODS = {
        "ORDERS_SNAPSHOT": ".ob-snap",
        "ORDERS_UPDATE": ".ob-inc",
        "TRADES_UPDATE": ".trades",
        "USER_BALANCES": "balance",
        "USER_ORDERS": "order",
        "USER_TRADES": "trade",
    }

    ORDER_STATES = {
        "DONE": {"done", "cancel", "partial-canceled", "reject", "fail"},
        "FAIL": {"reject", "fail"},
        "OPEN": {"submitted", "wait", "pending"},
        "CANCEL": {"partial-canceled", "cancel"},
        "CANCEL_WAIT": {'wait', 'cancel', 'done', 'reject'},
    }

    # Timeouts
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    API_CALL_TIMEOUT = 10.0
    API_MAX_RETRIES = 4

    # Intervals
    # Only used when nothing is received from WS
    SHORT_POLL_INTERVAL = 10.0
    # Two minutes should be fine since we get balances via WS
    LONG_POLL_INTERVAL = 120.0
    # Two minutes should be fine for order status since we get these via WS
    UPDATE_ORDER_STATUS_INTERVAL = 120.0
    # We don't get many messages here if we're not updating orders so set this pretty high
    USER_TRACKER_MAX_AGE = 300.0
    # 10 minute interval to update trading rules, these would likely never change whilst running.
    INTERVAL_TRADING_RULES = 600

    # Trading pair splitter regex
    TRADING_PAIR_SPLITTER = r"^(\w+)(btc|ltc|altm|doge|eth|try|eur|irt|bnb|usdt|usdc|usds|tusd|cro|roger)$"

    RL_TIME_INTERVAL = 12
    RL_ID_HTTP_ENDPOINTS = "AllHTTP"
    RL_ID_WS_ENDPOINTS = "AllWs"
    RL_ID_WS_AUTH = "AllWsAuth"
    RL_ID_TICKER = "Ticker"
    RL_ID_ORDER_BOOK = "OrderBook"
    RL_ID_ORDER_CREATE = "OrderCreate"
    RL_ID_ORDER_DELETE = "OrderDelete"
    RL_ID_ORDER_STATUS = "OrderStatus"
    RL_ID_USER_ORDERS = "OrdersUser"
    RL_HTTP_LIMIT = 30
    RL_WS_LIMIT = 50
    RATE_LIMITS = [
        RateLimit(
            limit_id=RL_ID_HTTP_ENDPOINTS,
            limit=RL_HTTP_LIMIT,
            time_interval=RL_TIME_INTERVAL
        ),
        # http
        RateLimit(
            limit_id=ENDPOINT["NETWORK_CHECK"],
            limit=RL_HTTP_LIMIT,
            time_interval=RL_TIME_INTERVAL,
            linked_limits=[LinkedLimitWeightPair(RL_ID_HTTP_ENDPOINTS)],
        ),
        RateLimit(
            limit_id=RL_ID_TICKER,
            limit=RL_HTTP_LIMIT,
            time_interval=RL_TIME_INTERVAL,
            linked_limits=[LinkedLimitWeightPair(RL_ID_HTTP_ENDPOINTS)],
        ),
        RateLimit(
            limit_id=ENDPOINT["SYMBOL"],
            limit=RL_HTTP_LIMIT,
            time_interval=RL_TIME_INTERVAL,
            linked_limits=[LinkedLimitWeightPair(RL_ID_HTTP_ENDPOINTS)],
        ),
        RateLimit(
            limit_id=RL_ID_ORDER_BOOK,
            limit=RL_HTTP_LIMIT,
            time_interval=RL_TIME_INTERVAL,
            linked_limits=[LinkedLimitWeightPair(RL_ID_HTTP_ENDPOINTS)],
        ),
        RateLimit(
            limit_id=RL_ID_ORDER_CREATE,
            limit=RL_HTTP_LIMIT,
            time_interval=RL_TIME_INTERVAL,
            linked_limits=[LinkedLimitWeightPair(RL_ID_HTTP_ENDPOINTS)],
        ),
        RateLimit(
            limit_id=RL_ID_ORDER_DELETE,
            limit=RL_HTTP_LIMIT,
            time_interval=RL_TIME_INTERVAL,
            linked_limits=[LinkedLimitWeightPair(RL_ID_HTTP_ENDPOINTS)],
        ),
        RateLimit(
            limit_id=RL_ID_ORDER_STATUS,
            limit=RL_HTTP_LIMIT,
            time_interval=RL_TIME_INTERVAL,
            linked_limits=[LinkedLimitWeightPair(RL_ID_HTTP_ENDPOINTS)],
        ),
        RateLimit(
            limit_id=RL_ID_USER_ORDERS,
            limit=RL_HTTP_LIMIT,
            time_interval=RL_TIME_INTERVAL,
            linked_limits=[LinkedLimitWeightPair(RL_ID_HTTP_ENDPOINTS)],
        ),
        RateLimit(
            limit_id=ENDPOINT["USER_BALANCES"],
            limit=RL_HTTP_LIMIT,
            time_interval=RL_TIME_INTERVAL,
            linked_limits=[LinkedLimitWeightPair(RL_ID_HTTP_ENDPOINTS)],
        ),
        # ws
        RateLimit(limit_id=RL_ID_WS_ENDPOINTS, limit=RL_WS_LIMIT, time_interval=RL_TIME_INTERVAL),
        RateLimit(
            limit_id=WS_EVENT_SUBSCRIBE,
            limit=RL_WS_LIMIT,
            time_interval=RL_TIME_INTERVAL,
            linked_limits=[LinkedLimitWeightPair(RL_ID_WS_ENDPOINTS)],
        ),
        RateLimit(
            limit_id=WS_EVENT_UNSUBSCRIBE,
            limit=RL_WS_LIMIT,
            time_interval=RL_TIME_INTERVAL,
            linked_limits=[LinkedLimitWeightPair(RL_ID_WS_ENDPOINTS)],
        ),
    ]
