import asyncio
import functools
from asyncio import Task
from decimal import Decimal
from typing import Dict, List, Optional, Union

from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.data_feed.coin_gecko_data_feed import CoinGeckoDataFeed
from hummingbot.data_feed.coin_gecko_data_feed.coin_gecko_constants import COOLOFF_AFTER_BAN


class CoinGeckoRateSource(RateSourceBase):
    def __init__(self, extra_token_ids: List[str]):
        super().__init__()
        self._coin_gecko_supported_vs_tokens: Optional[List[str]] = None
        self._coin_gecko_data_feed: Optional[CoinGeckoDataFeed] = None  # delayed because of circular reference
        self._extra_token_ids = extra_token_ids
        self._rate_limit_exceeded = asyncio.Event()
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return "coin_gecko"

    @property
    def extra_token_ids(self) -> List[str]:
        return self._extra_token_ids

    @extra_token_ids.setter
    def extra_token_ids(self, new_ids: List[str]):
        self._extra_token_ids = new_ids

    def try_event(self, fn):
        @functools.wraps(fn)
        async def try_raise_event(*args, **kwargs):
            while True:
                # If the rate limit has been exceeded, wait for the cool-off period to pass
                if self._rate_limit_exceeded.is_set():
                    await self._rate_limit_exceeded.wait()

                try:
                    res = await fn(*args, **kwargs)
                    return res
                except IOError as e:
                    # This is from exceeding the server's rate limit, signal the issue and wait for post-ban cool-off
                    self.logger().warning("Rate limit exceeded with:")
                    self.logger().warning(f"   {e}")
                    self.logger().warning("   Report to development team")
                    self._rate_limit_exceeded.set()
                    # This is the cool-off after a ban
                    await self._sleep(COOLOFF_AFTER_BAN)
                    self.logger().info(f"   Continuing after {COOLOFF_AFTER_BAN} seconds")
                    self._rate_limit_exceeded.clear()
                except Exception as e:
                    self.logger().error(f"Unhandled error in CoinGecko rate source response: {str(e)}", exc_info=True)
                    raise Exception(f"Unhandled error in CoinGecko rate source response: {str(e)}")

        return try_raise_event

    @async_ttl_cache(ttl=COOLOFF_AFTER_BAN, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        """
        Fetches the first 2500 CoinGecko prices ordered by market cap to ~ 500K USD

        :param quote_token: The quote token for which to fetch prices
        :return A dictionary of trading pairs and prices
        """
        await self._lock.acquire()

        if quote_token is None:
            raise NotImplementedError("Must supply a quote token to fetch prices for CoinGecko")
        self._ensure_data_feed()
        vs_currency = quote_token.lower()
        results = {}
        if not self._coin_gecko_supported_vs_tokens:
            self._coin_gecko_supported_vs_tokens = await self.try_event(
                self._coin_gecko_data_feed.get_supported_vs_tokens)()

        if vs_currency not in self._coin_gecko_supported_vs_tokens:
            vs_currency = "usd"

        # Extra tokens
        r = await self.try_event(self._get_coin_gecko_extra_token_prices)(vs_currency)
        results.update(r)

        # Coin Gecko returns 250 assets max per page, 2500th is around 500K USD market cap (as of 2/2023)
        tasks: List[Task] = []
        for page_no in range(1, 8):
            tasks.append(asyncio.create_task(self._get_coin_gecko_prices_by_page(vs_currency, page_no, None)))

        try:
            task_results = await self.try_event(safe_gather)(*tasks, return_exceptions=False)
        except Exception:
            self.logger().error(
                "Unexpected error while retrieving rates from Coingecko. Check the log file for more info.")
            raise

        # Collect the results
        for i, task_result in enumerate(task_results):
            results.update(task_result)

        self._lock.release()
        return results

    def _ensure_data_feed(self):
        if self._coin_gecko_data_feed is None:
            self._coin_gecko_data_feed = CoinGeckoDataFeed()

    async def _get_coin_gecko_prices_by_page(self,
                                             vs_currency: str,
                                             page_no: int,
                                             category: Union[str, None]) -> Dict[str, Decimal]:
        """
        Fetches CoinGecko prices by page number.

        :param vs_currency: A currency (crypto or fiat) to get prices of tokens in, see
        https://api.coingecko.com/api/v3/simple/supported_vs_currencies for the current supported list
        :param page_no: The page number
        :param category | None: category to filter tokens to get from the provider (specifying one limits to 50 results)

        :return: A dictionary of trading pairs and prices (50 results max if a category is provided)
        """
        results = {}
        resp = await self.try_event(self._coin_gecko_data_feed.get_prices_by_page)(vs_currency=vs_currency,
                                                                                   page_no=page_no, category=category)

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
        # TODO: Should we force hummingbot to be included?
        # self._extra_token_ids.append("hummingbot") - This fails the tests, not sure why
        if self._extra_token_ids:
            resp = await self.try_event(self._coin_gecko_data_feed.get_prices_by_token_id)(vs_currency=vs_currency,
                                                                                           token_ids=self._extra_token_ids)
            for record in resp:
                pair = combine_to_hb_trading_pair(base=record["symbol"].upper(), quote=vs_currency.upper())
                if record["current_price"]:
                    results[pair] = Decimal(str(record["current_price"]))
        return results

    async def _sleep(self, delay: float):
        await asyncio.sleep(delay)
