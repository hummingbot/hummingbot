import asyncio
from asyncio import Task
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

    # get_prices() is tuned to call the API about 50 times, close to the rate limit of 50calls/60s
    # No point trying to call again sooner than a minute
    @async_ttl_cache(ttl=72, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        """
        Fetches CoinGecko prices for the top 800-ish tokens (order by market cap) of each of these categories,
        each call (when specifying categories) returns 50 per page
             cryptocurrency
             decentralized-exchange
             decentralized-finance-defi
             smart-contract-platform
             stablecoins
             wrapped-tokens

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

        filled: Dict[str, bool] = {c: False for c in CONSTANTS.TOKEN_CATEGORIES}
        page_no: int = 1

        # Coin Gecko returns 50 assets max when called with a category
        # The algorithm is to query assets/category until we reached either
        #   - The end of a category in which case the returned list < 50
        #   - Or the approximate number of calls that would total the assets to about 1000
        #     (at the time of implementation, 10 would actually fill all the categories)
        #     10 has been tested as providing +900 assets on 10/20/2022
        while not all(filled[c] for c in CONSTANTS.TOKEN_CATEGORIES) and page_no <= 10:
            tasks: List[Task] = []
            called: List[str] = []

            # The API calls could be lengthy, parallel execution, but for the same page,
            # so it detects when a category has been completed
            for category in CONSTANTS.TOKEN_CATEGORIES:
                if not filled[category]:
                    tasks.append(
                        asyncio.create_task(self._get_coin_gecko_prices_by_page(vs_currency, page_no, category)))
                    called.append(category)

            while True:
                try:
                    task_results = await safe_gather(*tasks, return_exceptions=False)
                    break
                except IOError:
                    # This is from exceeding the server's rate limit, silently try to correct
                    pass
                except Exception:
                    self.logger().error(
                        "Unexpected error while retrieving rates from Coingecko. Check the log file for more info.")
                    raise
                finally:
                    # In the rare case (hopefully) of server/client time slew, wait for the release of
                    # as many cool-off as the number of requests in the gathered tasks. Add 5%
                    await asyncio.sleep(
                        self._coin_gecko_data_feed.rate_limit_retry_s * len(CONSTANTS.TOKEN_CATEGORIES) * 1.05)

            # Collect the results while detecting an exception that is not a rate limit excess
            for i, task_result in enumerate(task_results):
                results.update(task_result)
                filled[called[i]] = len(task_result) < 50
            # Next page calls
            page_no = page_no + 1

        # Additional tokens, possibly not in the top tokens/category
        results.update(await self._get_coin_gecko_extra_token_prices(vs_currency))

        return results

    def _ensure_data_feed(self):
        if self._coin_gecko_data_feed is None:
            self._coin_gecko_data_feed = CoinGeckoDataFeed.get_instance()

    async def _get_coin_gecko_prices_by_page(self, vs_currency: str, page_no: int, category: str) -> Dict[str, Decimal]:
        """
        Fetches CoinGecko prices by page number.

        :param vs_currency: A currency (crypto or fiat) to get prices of tokens in, see
        https://api.coingecko.com/api/v3/simple/supported_vs_currencies for the current supported list
        :param page_no: The page number
        :param category: category to filter tokens to get from the provider (specifying one limits to 50 results)

        :return: A dictionary of trading pairs and prices (50 results max)
        """
        results = {}
        while True:
            try:
                resp = await self._coin_gecko_data_feed.get_prices_by_page(
                    vs_currency=vs_currency, page_no=page_no, category=category
                )
                for record in resp:
                    pair = combine_to_hb_trading_pair(base=record['symbol'].upper(), quote=vs_currency.upper())
                    if record["current_price"]:
                        results[pair] = Decimal(str(record["current_price"]))
                return results
            except Exception:
                # This method should be called in a gather with 'return_exceptions=False', simply pass the exception
                # up to the gather to try to cancel other parallel tasks and handle the re-submission
                raise

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
