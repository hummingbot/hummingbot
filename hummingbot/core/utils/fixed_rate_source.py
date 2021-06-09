from decimal import Decimal

from hummingbot.core.rate_oracle.utils import find_rate


class FixedRateSource:

    def __init__(self):
        super().__init__()

        self._known_rates: dict = {}

    def __str__(self):
        return "fixed rates"

    def add_rate(self, token_pair: str, rate: Decimal):
        """Add the fixed rate to the rate source
        :param token_pair: A trading pair, e.g. BTC-USDT
        :param rate: The rate to associate to the token pair
        """
        self._known_rates[token_pair] = rate

    def rate(self, pair: str) -> Decimal:
        """
        Finds a conversion rate for a given symbol, this can be direct or indirect prices as long as it can find a route
        to achieve this.
        :param pair: A trading pair, e.g. BTC-USDT
        :return A conversion rate
        """
        return find_rate(self._known_rates, pair)
