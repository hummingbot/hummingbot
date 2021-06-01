# A single source of truth for constant variables related to the exchange
class Constants:
    EXCHANGE_NAME = "gate_io"
    REST_URL = "https://api.gateio.ws/api/v4"
    REST_URL_AUTH = "/api/v4"
    WS_URL = "wss://api.gateio.ws/ws/v4/"

    HBOT_BROKER_ID = "HBOT"

    ENDPOINT = {
        # Public Endpoints
        "TICKER": "spot/tickers",
        "SYMBOL": "spot/currency_pairs",
        "CURRENCY": "spot/currencies/{currency}",
        "ORDER_BOOK": "spot/order_book",
        "ORDER_CREATE": "spot/orders",
        "ORDER_DELETE": "order/{id}",
        "ORDER_STATUS": "order/{id}",
        "USER_ORDERS": "order",
        "USER_BALANCES": "spot/accounts",
    }

    WS_SUB = {
        "TRADES": "spot.trades",
        "ORDERS_SNAPSHOT": "spot.order_book",
        "ORDERS_UPDATE": "spot.order_book_update",
        "USER_TRADES": "spot.usertrades",
        "USER_ORDERS": "spot.orders",
        "USER_BALANCE": "spot.balances",

    }

    WS_METHODS = {
        "TRADES_SNAPSHOT": "snapshotTrades",
        "USER_BALANCE": "getTradingBalance",
        "USER_ORDERS": "activeOrders",
        "USER_TRADES": "report",
    }

    # Timeouts
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    API_CALL_TIMEOUT = 10.0
    API_MAX_RETRIES = 4

    # Intervals
    # Only used when nothing is received from WS
    SHORT_POLL_INTERVAL = 5.0
    # One minute should be fine since we get trades, orders and balances via WS
    LONG_POLL_INTERVAL = 60.0
    UPDATE_ORDER_STATUS_INTERVAL = 60.0
    # 10 minute interval to update trading rules, these would likely never change whilst running.
    INTERVAL_TRADING_RULES = 600
