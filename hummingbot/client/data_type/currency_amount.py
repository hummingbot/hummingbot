from collections import namedtuple


class CurrencyAmount(namedtuple("_CurrencyAmount", "token, amount")):
    token: str
    amount: float