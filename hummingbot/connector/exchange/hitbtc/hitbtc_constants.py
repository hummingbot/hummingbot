# A single source of truth for constant variables related to the exchange
class Constants:
    EXCHANGE_NAME = "hitbtc"
    REST_URL = "https://api.hitbtc.com/api/2"
    REST_URL_AUTH = "/api/2"
    WS_PRIVATE_URL = "wss://api.hitbtc.com/api/2/ws/trading"
    WS_PUBLIC_URL = "wss://api.hitbtc.com/api/2/ws/public"

    HBOT_BROKER_ID = "refzzz48"

    ENDPOINT = {
        # Public Endpoints
        "TICKER": "public/ticker",
        "TICKER_SINGLE": "public/ticker/{trading_pair}",
        "SYMBOL": "public/symbol",
        "ORDER_BOOK": "public/orderbook",
        "ORDER_CREATE": "order",
        "ORDER_DELETE": "order/{id}",
        "ORDER_STATUS": "order/{id}",
        "USER_ORDERS": "order",
        "USER_BALANCES": "trading/balance",
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

    # Trading pair splitter regex
    TRADING_PAIR_SPLITTER = r"^(\w+)(BTC|BCH|DAI|DDRST|EOSDT|EOS|ETH|EURS|HIT|IDRT|PAX|BUSD|GUSD|TUSD|USDC|USDT|USD)$"
