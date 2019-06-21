from collections import namedtuple


class CurrencyAmount(namedtuple("_CurrencyAmount", "token, amount")):
    token: str
    amount: float

    def __init__(self):
        self.token = None
        self.amount = None