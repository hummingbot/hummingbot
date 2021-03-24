# A single source of truth for constant variables related to the exchange
class Constants:
    """
    API Documentation Links:
    https://api-docs.coinzoom.com/
    https://api-markets.coinzoom.com/
    """
    EXCHANGE_NAME = "coinzoom"
    REST_URL = "https://api.stage.coinzoom.com/api/v1/public"
    WS_PRIVATE_URL = "wss://api.stage.coinzoom.com/api/v1/public/market/data/stream"
    WS_PUBLIC_URL = "wss://api.stage.coinzoom.com/api/v1/public/market/data/stream"

    HBOT_BROKER_ID = "refzzz48"

    ENDPOINT = {
        # Public Endpoints
        "TICKER": "marketwatch/ticker",
        "SYMBOL": "instruments",
        "ORDER_BOOK": "marketwatch/orderbook/{trading_pair}/150/2",
        "ORDER_CREATE": "order",
        "ORDER_DELETE": "order/{id}",
        "ORDER_STATUS": "order/{id}",
        "USER_ORDERS": "order",
        "USER_BALANCES": "ledger/list",
    }

    WS_SUB = {
        "TRADES": "TradeSummaryRequest",
        "ORDERS": "OrderBookRequest",
        "USER_ORDERS_TRADES": ["OrderUpdateRequest"],

    }

    WS_METHODS = {
        "ORDERS_SNAPSHOT": "ob",
        "ORDERS_UPDATE": "oi",
        "TRADES_UPDATE": "ts",
        "USER_BALANCE": "getTradingBalance",
        "USER_ORDERS": "OrderResponse",
        "USER_ORDERS_CANCEL": "OrderCancelResponse",
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
