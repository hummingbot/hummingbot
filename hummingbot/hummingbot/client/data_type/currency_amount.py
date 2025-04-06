
class CurrencyAmount:

    def __init__(self):
        self._token: str = None
        self._amount: float = None

    @property
    def token(self) -> str:
        return self._token

    @token.setter
    def token(self, token: str):
        self._token = token

    @property
    def amount(self) -> float:
        return self._amount

    @amount.setter
    def amount(self, amount: float):
        self._amount = amount
