from enum import Enum


class GrvtOrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"


class GrvtTimeInForce(str, Enum):
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    POST_ONLY = "post_only"


class GrvtChannel(str, Enum):
    ORDERBOOK = "orderbook"
    TRADES = "trades"
    FUNDING = "funding"
    ORDERS = "orders"
    FILLS = "fills"
    POSITIONS = "positions"
