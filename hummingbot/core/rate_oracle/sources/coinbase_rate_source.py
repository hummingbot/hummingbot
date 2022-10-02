from decimal import Decimal
from typing import Dict, Optional

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

REST_CALL_RATE_LIMIT_ID = "coinbase_rate_limit_id"
RATE_LIMITS = [RateLimit(REST_CALL_RATE_LIMIT_ID, limit=50, time_interval=60)]


class CoinbaseRateSource(RateSourceBase):
    def __init__(self):
        super().__init__()
        async_throttler = AsyncThrottler(rate_limits=RATE_LIMITS)
        self._api_factory = WebAssistantsFactory(throttler=async_throttler)

    @property
    def name(self) -> str:
        return "coinbase"

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        """
        Fetches Coinbase prices from coinbase.com where only MNT and USD pair
        :return A dictionary of trading pairs and prices
        """
        results = {}
        tasks = [
            self.get_coinbase_prices_by_currency("MNT"),
            self.get_coinbase_prices_by_currency("USD"),
            self.get_coinbase_prices_by_currency(quote_token)
        ]
        task_results = await safe_gather(*tasks, return_exceptions=True)
        for task_result in task_results:
            if isinstance(task_result, Exception):
                self.logger().error(task_result)
                self.logger().error(
                    "Unexpected error while retrieving rates from Coinbase. " "Check the log file for more info."
                )
                break
            else:
                results.update(task_result)
        return results

    async def get_coinbase_prices_by_currency(self, currency: str) -> Dict[str, Decimal]:
        """
        Fetches Coinbase exchange rates.
        :param vs_currency: A currency (crypto or fiat) to get prices of tokens in, see
        https://api.coinbase.com/v2/currencies for the current supported list
        :param currency
        :return A dictionary of fiat rates
        """
        results = {}
        rest_assistant = await self._api_factory.get_rest_assistant()
        price_url = "https://api.coinbase.com/v2/exchange-rates"
        request_result = await rest_assistant.execute_request(
            method=RESTMethod.GET,
            url=price_url,
            throttler_limit_id=REST_CALL_RATE_LIMIT_ID,
            params={
                "currency": currency
            }
        )
        rates = request_result["data"]["rates"]
        for quote, price in rates.items():
            pair = f"{currency}-{quote.upper()}"
            results[pair] = Decimal(str(price))
        return results
