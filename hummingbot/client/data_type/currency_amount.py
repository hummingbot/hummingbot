
class CurrencyAmount:

    def __init__(self):
        self._token = None
        self._amount = None

    def set_token(self, token: str):
        self._token = token

    def get_token(self) -> str:
        return self._token

    def set_amount(self, amount: float):
        self._amount = amount

    def get_amount(self) -> float:
        return self._amount

    def add_amount(self, amount: float):
        self._amount += amount

    def subtract_amount(self, amount: float):
        self._amount -= amount
