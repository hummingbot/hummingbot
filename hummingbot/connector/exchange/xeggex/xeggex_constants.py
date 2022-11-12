# A single source of truth for constant variables related to the exchange
class Constants:
    EXCHANGE_NAME = "xeggex"
    REST_URL = "https://xeggex.com/api/v2"
    WS_PRIVATE_URL = "wss://ws.xeggex.com"
    WS_PUBLIC_URL = "wss://ws.xeggex.com"

    HBOT_BROKER_ID = "HUMBOT"

    ENDPOINT = {
        # Public Endpoints REST API
        "TICKER": "tickers",
        "TICKER_SINGLE": "ticker/{trading_pair}",
        "SYMBOL": "market/getlist",
        "ORDER_BOOK": "orderbook",
        "ORDER_CREATE": "createorder",
        "ORDER_DELETE": "cancelorder",
        "ORDER_STATUS": "getorder/{id}",
        "USER_ORDERS": "getorders",
        "USER_BALANCES": "balances",
    }

    WS_SUB = {
        "TRADES": "Trades",
        "ORDERS": "Orderbook",
        "USER_ORDERS_TRADES": "Reports",

    }

    WS_METHODS = {
        "ORDERS_SNAPSHOT": "snapshotOrderbook",
        "ORDERS_UPDATE": "updateOrderbook",
        "TRADES_SNAPSHOT": "snapshotTrades",
        "TRADES_UPDATE": "updateTrades",
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
