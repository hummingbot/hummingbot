from hummingbot.client.data_type.currency_amount import CurrencyAmount
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion


class PerformanceAnalysis:

    def __init__(self):
        self._starting_base = CurrencyAmount()
        self._starting_quote = CurrencyAmount()
        self._current_base = CurrencyAmount()
        self._current_quote = CurrencyAmount()

    def _get_currency_amount_pair(self, is_base: bool, is_starting: bool) -> CurrencyAmount:
        """ Helper method to select the correct CurrencyAmount pair. """
        if is_base and is_starting:
            return self._starting_base
        elif not is_base and is_starting:
            return self._starting_quote
        elif is_base and not is_starting:
            return self._current_base
        else:
            return self._current_quote

    def add_balances(self, asset_name: str, amount: float, is_base: bool, is_starting: bool):
        """ Adds the balance of either the base or the quote in the given market symbol pair token to the corresponding
        CurrencyAmount object. """
        currency_amount = self._get_currency_amount_pair(is_base, is_starting)
        if currency_amount.get_token() is None:
            currency_amount.set_token(asset_name)
            currency_amount.set_amount(amount)
        else:
            if currency_amount.get_token() == asset_name:
                currency_amount.add_amount(amount)
            else:
                erc = ExchangeRateConversion.get_instance()
                temp_amount = erc.convert_token_value(amount, asset_name, currency_amount.get_token())
                currency_amount.add_amount(temp_amount)

    def compute_profitability(self, price: float) -> float:
        """ Compute the profitability of the trading bot based on the starting and current prices"""
        starting_amount = (self._starting_base.get_amount() * price) + self._starting_quote.get_amount()
        current_amount = (self._current_base.get_amount() * price) + self._current_quote.get_amount()
        percent = ((current_amount / starting_amount) - 1) * 100
        return percent
