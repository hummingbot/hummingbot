

class SymbolPair:

    def __init__(self, base_currency: str, quote_currency: str):
        self._base_currency: str = base_currency
        self._quote_currency: str = quote_currency

    @property
    def symbol(self):
        return self._base_currency + self._quote_currency

    @property
    def base_currency(self):
        return self._base_currency

    @property
    def quote_currency(self):
        return self._quote_currency
