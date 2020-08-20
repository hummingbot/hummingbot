from decimal import Decimal

CRYPTO_QUOTES = [
    "XBT",
    "ETH",
    "USDT",
    "DAI",
    "USDC",
]

ADDED_CRYPTO_QUOTES = [
    "XXBT",
    "XETH",
    "BTC",
]

FIAT_QUOTES = [
    "USD",
    "EUR",
    "CAD",
    "JPY",
    "GBP",
    "CHF",
    "AUD"
]

FIAT_QUOTES = ["Z" + quote for quote in FIAT_QUOTES] + FIAT_QUOTES

QUOTES = CRYPTO_QUOTES + ADDED_CRYPTO_QUOTES + FIAT_QUOTES

BASE_ORDER_MIN = {
    "ALGO": Decimal("50"),
    "XREP": Decimal("0.3"),
    "BAT": Decimal("50"),
    "BTC": Decimal("0.002"),
    "XBT": Decimal("0.002"),
    "BCH": Decimal("0.000002"),
    "ADA": Decimal("1"),
    "LINK": Decimal("10"),
    "ATOM": Decimal("1"),
    "DAI": Decimal("10"),
    "DASH": Decimal("0.03"),
    "XDG": Decimal("3000"),
    "EOS": Decimal("3"),
    "ETH": Decimal("0.02"),
    "ETC": Decimal("0.3"),
    "GNO": Decimal("0.02"),
    "ICX": Decimal("50"),
    "LSK": Decimal("10"),
    "LTC": Decimal("0.1"),
    "XMR": Decimal("0.1"),
    "NANO": Decimal("10"),
    "OMG": Decimal("10"),
    "PAXG": Decimal("0.01"),
    "QTUM": Decimal("0.1"),
    "XRP": Decimal("30"),
    "SC": Decimal("5000"),
    "XLM": Decimal("30"),
    "USDT": Decimal("5"),
    "XTZ": Decimal("1"),
    "USDC": Decimal("5"),
    "MLN": Decimal("0.1"),
    "WAVES": Decimal("10"),
    "ZEC": Decimal("0.03"),
    "TRX": Decimal("500")
}
