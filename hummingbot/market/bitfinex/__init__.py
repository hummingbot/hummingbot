import re

BITFINEX_REST_URL = "https://api-pub.bitfinex.com/v2"
BITFINEX_WS_URI = "wss://api-pub.bitfinex.com/ws/2"

TRADING_PAIR_SPLITTER = re.compile(r"^(\w+)(BTC|ETH|BNB|XRP|USD|USDT|USDC|USDS|TUSD|PAX|TRX|BUSD|NGN)$")


class SubmitOrder:
    OID = 0

    def __init__(self, oid):
        self.oid = str(oid)

    @classmethod
    def parse(cls, order_snapshot):
        return cls(order_snapshot[cls.OID])
