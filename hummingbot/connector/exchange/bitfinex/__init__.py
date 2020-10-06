from decimal import Decimal

BITFINEX_REST_URL_V1 = "https://api.bitfinex.com/v1"
BITFINEX_REST_URL = "https://api-pub.bitfinex.com/v2"
BITFINEX_REST_AUTH_URL = "https://api.bitfinex.com/v2"
BITFINEX_WS_URI = "wss://api-pub.bitfinex.com/ws/2"
BITFINEX_WS_AUTH_URI = "wss://api.bitfinex.com/ws/2"

# this values ​​set by empirically way, because the bitfinex-market does not have
# these values. maybe later it will be in market-api.
TAKER_FEE = Decimal("0.002")
MAKER_FEE = Decimal("0.001")
AFF_CODE = "-dxCUrjvc"


class SubmitOrder:
    OID = 0

    def __init__(self, oid):
        self.oid = str(oid)

    @classmethod
    def parse(cls, order_snapshot):
        return cls(order_snapshot[cls.OID])


class OrderStatus:
    """
    full statuses, not all uses.
    Order Status:
    ACTIVE,
    EXECUTED @ PRICE(AMOUNT) e.g. "EXECUTED @ 107.6(-0.2)",
    PARTIALLY FILLED @ PRICE(AMOUNT),
    CANCELED,
    RSN_DUST
    RSN_PAUSE
    """
    ACTIVE = "ACTIVE"
    CANCELED = "CANCELED"
    PARTIALLY = "PARTIALLY"
    EXECUTED = "EXECUTED"


class ContentEventType:
    ORDER_UPDATE = "ou"
    TRADE_UPDATE = "tu"
    TRADE_EXECUTE = "te"
    WALLET_SNAPSHOT = "ws"
    WALLET_UPDATE = "wu"
    HEART_BEAT = "hb"
    AUTH = "auth"
    INFO = "info"
