from typing import Tuple

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
        CurrencyAmount object.

        NOTE: This is not to say that base / quote pairs between different markets are equivalent because that is NOT
        the case. Instead, this method will determine the current conversion rate between two stable coins before
        adding the balance to the corresponding CurrencyAmount object. Additionally, since it is possible that the
        exchange rate varies from the starting time of the bot to the current time, this conversion will always be
        performed using the SAME conversion rate - that is, the current conversion rate.

        So for example, let's say we are trading WETH/DAI and ETH/USD. Let's also assume that in  the
        hummingbot_application class, the first MarketSymbolPair in the market_symbol_pair list is WETH/DAI. This means
        that in theory, the base and quote balances will be computed in terms of WETH and DAI, respectively. When the
        ETH and USD balances are added to those of WETH and DAI, the token conversion method - see
        erc.convert_token_value() will be called to convert the currencies using the CURRENT conversion rate. The
        current WETH/ETH conversion rate as well as the current DAI/USD conversion rates will be used for BOTH the
        starting and the current balance to ensure that any changes in the conversion rates while the bot was running
        do not affect the performance analysis feature."""
        currency_amount = self._get_currency_amount_pair(is_base, is_starting)
        if currency_amount.token is None:
            currency_amount.token = asset_name
            currency_amount.amount = amount
        else:
            if currency_amount.token == asset_name:
                currency_amount.amount += amount
            else:
                erc = ExchangeRateConversion.get_instance()
                temp_amount = erc.convert_token_value(amount, asset_name, currency_amount.token, source="any")
                currency_amount.amount += temp_amount

    def compute_starting(self, price: float) -> Tuple[str, float]:
        """ Computes the starting amount of token between both exchanges. """
        starting_amount = (self._starting_base.amount * price) + self._starting_quote.amount
        starting_token = self._starting_quote.token
        return starting_token, starting_amount

    def compute_current(self, price: float) -> Tuple[str, float]:
        """ Computes the current amount of token between both exchanges. """
        current_amount = (self._current_base.amount * price) + self._current_quote.amount
        current_token = self._current_quote.token
        return current_token, current_amount

    def compute_delta(self, price: float) -> Tuple[str, float]:
        """ Computes the delta between current amount in exchange and starting amount. """
        starting_token, starting_amount = self.compute_starting(price)
        _, current_amount = self.compute_current(price)
        delta = current_amount - starting_amount
        return starting_token, delta

    def compute_return(self, price: float) -> float:
        """ Compute the profitability of the trading bot based on the starting and current prices """
        _, starting_amount = self.compute_starting(price)
        if starting_amount == 0:
            return float('nan')
        _, delta = self.compute_delta(price)
        percent = (delta / starting_amount) * 100
        return percent
