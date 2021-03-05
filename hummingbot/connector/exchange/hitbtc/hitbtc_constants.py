# A single source of truth for constant variables related to the exchange
class Constants:
    EXCHANGE_NAME = "hitbtc"
    REST_URL = "https://api.hitbtc.com/api/2"
    # WS_PRIVATE_URL = "wss://stream.crypto.com/v2/user"
    WS_PRIVATE_URL = "wss://api.hitbtc.com/api/2/ws/trading"
    # WS_PUBLIC_URL = "wss://stream.crypto.com/v2/market"
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
        "USER_BALANCES": "account/balance",
    }

    WS_SUB = {
        "TRADES": "Trades",
        "ORDERS": "Orderbook",
        "USER_ORDERS_TRADES": "Reports",

    }

    WS_METHODS = {
        "ORDER_SNAPSHOT": "snapshotOrderbook",
        "ORDER_UPDATE": "updateOrderbook",
        "TRADES_SNAPSHOT": "snapshotTrades",
        "TRADES_UPDATE": "updateTrades",
        "USER_ORDERS": "activeOrders",
        "USER_TRADES": "report",
    }

    API_REASONS = {
        0: "Success",
        403: "Action is forbidden for account",  # HTTP: 401
        429: "Too many requests",  # HTTP: 429
        500: "Internal Server Error",  # HTTP: 500
        503: "Service Unavailable",  # HTTP: 503
        504: "Gateway Timeout",  # HTTP: 504
        1001: "Authorization required",  # HTTP: 401
        1002: "Authorization required or has been failed",  # HTTP: 401
        1003: "Action forbidden for this API key",  # HTTP: 403
        1004: "Unsupported authorization method",  # HTTP: 401
        2001: "Symbol not found",  # HTTP: 400
        2002: "Currency not found",  # HTTP: 400
        2010: "Quantity not a valid number",  # HTTP: 400
        2011: "Quantity too low",  # HTTP: 400
        2012: "Bad quantity",  # HTTP: 400
        2020: "Price not a valid number",  # HTTP: 400
        2021: "Price too low",  # HTTP: 400
        2022: "Bad price",  # HTTP: 400
        20001: "Insufficient funds",  # HTTP: 400
        20002: "Order not found",  # HTTP: 400
        20003: "Limit exceeded",  # HTTP: 400
        20004: "Transaction not found",  # HTTP: 400
        20005: "Payout not found",  # HTTP: 400
        20006: "Payout already committed",  # HTTP: 400
        20007: "Payout already rolled back",  # HTTP: 400
        20008: "Duplicate clientOrderId",  # HTTP: 400
        20009: "Price and quantity not changed",  # HTTP: 400
        20010: "Exchange temporary closed",  # HTTP: 400
        20011: "Payout address is invalid",  # HTTP: 400
        20014: "Offchain for this payout is unavailable",  # HTTP: 400
        20032: "Margin account or position not found",  # HTTP: 400
        20033: "Position not changed",  # HTTP: 400
        20034: "Position in close only state",  # HTTP: 400
        20040: "Margin trading forbidden",  # HTTP: 400
        20080: "Internal order execution deadline exceeded",  # HTTP: 400.
        10001: "Validation error",  # HTTP: 400
        10021: "User disabled",  # HTTP: 400

    }

    # Timeouts
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    API_CALL_TIMEOUT = 10.0

    # Intervals
    # Only used when nothing is received from WS
    SHORT_POLL_INTERVAL = 5.0
    # HitBTC poll interval can't be too long since we don't get balances via websockets
    LONG_POLL_INTERVAL = 20.0
    # One minute should be fine for order status since we get these via WS
    UPDATE_ORDER_STATUS_INTERVAL = 60.0

    # Trading pair splitter regex
    TRADING_PAIR_SPLITTER = r"^(\w+)(BTC|BCH|DAI|DDRST|EOSDT|EOS|ETH|EURS|IDRT|PAX|BUSD|GUSD|TUSD|USDC|USD)$"
