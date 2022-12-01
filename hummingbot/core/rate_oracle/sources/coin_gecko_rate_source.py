import asyncio
from decimal import Decimal
from typing import Dict, List, Optional

from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.data_feed.coin_gecko_data_feed import CoinGeckoDataFeed, coin_gecko_constants as CONSTANTS


class CoinGeckoRateSource(RateSourceBase):
    def __init__(self, extra_token_ids: List[str]):
        super().__init__()
        self._coin_gecko_supported_vs_tokens: Optional[List[str]] = None
        self._coin_gecko_data_feed: Optional[CoinGeckoDataFeed] = None  # delayed because of circular reference
        self._extra_token_ids = extra_token_ids

    @property
    def name(self) -> str:
        return "coin_gecko"

    @property
    def extra_token_ids(self) -> List[str]:
        return self._extra_token_ids

    @extra_token_ids.setter
    def extra_token_ids(self, new_ids: List[str]):
        self._extra_token_ids = new_ids

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        """
        Fetches CoinGecko prices for the top 1000 token (order by market cap), each API query returns 250 results,
        hence it queries 4 times concurrently.

        :param quote_token: The quote token for which to fetch prices
        :return A dictionary of trading pairs and prices
        """
        if quote_token is None:
            raise NotImplementedError("Must supply a quote token to fetch prices for CoinGecko")
        self._ensure_data_feed()
        vs_currency = quote_token.lower()
        results = {}
        if not self._coin_gecko_supported_vs_tokens:
            self._coin_gecko_supported_vs_tokens = await self._coin_gecko_data_feed.get_supported_vs_tokens()
        if vs_currency not in self._coin_gecko_supported_vs_tokens:
            vs_currency = "usd"
        tasks = [
            asyncio.get_event_loop().create_task(self._get_coin_gecko_prices_by_page(vs_currency, i, category))
            for i in range(1, 3)
            for category in CONSTANTS.TOKEN_CATEGORIES
        ]
        tasks.append(asyncio.get_event_loop().create_task(self._get_coin_gecko_extra_token_prices(vs_currency)))
        task_results = await safe_gather(*tasks, return_exceptions=True)
        for task_result in task_results:
            if isinstance(task_result, Exception):
                self.logger().error(
                    "Unexpected error while retrieving rates from Coingecko. Check the log file for more info.",
                    exc_info=task_result,
                )
            else:
                results.update(task_result)
        return results

    def _ensure_data_feed(self):
        if self._coin_gecko_data_feed is None:
            self._coin_gecko_data_feed = CoinGeckoDataFeed()

    async def _get_coin_gecko_prices_by_page(self, vs_currency: str, page_no: int, category: str) -> Dict[str, Decimal]:
        """
        Fetches CoinGecko prices by page number.

        :param vs_currency: A currency (crypto or fiat) to get prices of tokens in, see
        https://api.coingecko.com/api/v3/simple/supported_vs_currencies for the current supported list
        :param page_no: The page number
        :param category: category to filter tokens to get from the provider

        :return: A dictionary of trading pairs and prices (250 results max)
        """
        results = {}
        resp = await self._coin_gecko_data_feed.get_prices_by_page(
            vs_currency=vs_currency, page_no=page_no, category=category
        )

        for record in resp:
            pair = combine_to_hb_trading_pair(base=record['symbol'].upper(), quote=vs_currency.upper())
            if record["current_price"]:
                results[pair] = Decimal(str(record["current_price"]))
        return results

    async def _get_coin_gecko_extra_token_prices(self, vs_currency: str) -> Dict[str, Decimal]:
        """
        Fetches CoinGecko prices for the configured extra tokens.

        :param vs_currency: A currency (crypto or fiat) to get prices of tokens in, see
        https://api.coingecko.com/api/v3/simple/supported_vs_currencies for the current supported list

        :return: A dictionary of trading pairs and prices
        """
        results = {}
        if self._extra_token_ids:
            resp = await self._coin_gecko_data_feed.get_prices_by_token_id(
                vs_currency=vs_currency, token_ids=self._extra_token_ids
            )
            for record in resp:
                pair = combine_to_hb_trading_pair(base=record["symbol"].upper(), quote=vs_currency.upper())
                if record["current_price"]:
                    results[pair] = Decimal(str(record["current_price"]))
        return results
