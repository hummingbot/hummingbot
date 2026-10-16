from decimal import Decimal
from typing import Dict, Optional

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache
from hummingbot.data_feed.coin_paprika_data_feed import CoinPaprikaDataFeed, coin_paprika_constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class CoinPaprikaRateSource(RateSourceBase):
    """
    A rate source backed by the keyless CoinPaprika API (https://api.coinpaprika.com/v1).

    A single request to the /tickers endpoint returns prices for all active coins, quoted in any of
    the currencies the endpoint supports (USD, EUR, BTC, ETH and other fiat currencies). Responses
    are cached to stay within the keyless plan's request quota.
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(self):
        self._coin_paprika_data_feed = CoinPaprikaDataFeed()

    @property
    def name(self) -> str:
        return "coin_paprika"

    async def start_network(self):
        await self._coin_paprika_data_feed.start_network()

    async def stop_network(self):
        await self._coin_paprika_data_feed.stop_network()

    async def check_network(self) -> NetworkStatus:
        return await self._coin_paprika_data_feed.check_network()

    @async_ttl_cache(ttl=CONSTANTS.TICKERS_CACHE_TTL, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        """
        Fetches the prices of all active coins on coinpaprika.com against the given quote token.

        When the requested quote token is not supported by the /tickers endpoint, USD quotes are
        returned instead (the same fallback the CoinGecko rate source applies).

        :param quote_token: The quote token for which to fetch prices
        :return: A dictionary of trading pairs and prices
        """
        quote_token = (quote_token or CONSTANTS.UNIVERSAL_QUOTE_TOKEN).upper()
        if not self._coin_paprika_data_feed.is_quote_token_supported(quote_token):
            self.logger().warning(
                f"CoinPaprikaRateSource does not support {quote_token} as the quote token."
                f" Using {CONSTANTS.UNIVERSAL_QUOTE_TOKEN} quotes instead."
            )
            quote_token = CONSTANTS.UNIVERSAL_QUOTE_TOKEN
        return await self._coin_paprika_data_feed.get_all_prices(quote_token=quote_token)
