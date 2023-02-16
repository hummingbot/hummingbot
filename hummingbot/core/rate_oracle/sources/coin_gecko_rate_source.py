import asyncio
from asyncio import Task
from decimal import Decimal
from typing import Dict, List, Optional, Union

from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.data_feed.coin_gecko_data_feed import CoinGeckoDataFeed, coin_gecko_constants as CONSTANTS
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

    # get_prices() is tuned to call the API about 50 times, close to the rate limit of 50calls/60s
    # No point trying to call again sooner than a minute
    @async_ttl_cache(ttl=COOLOFF_AFTER_BAN, maxsize=1)
    async def get_prices_category(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        """
        WARNING: This method is not as efficient since the rate is very stringent. Each call needs to return more info

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
        await self._lock.acquire()

        if quote_token is None:
            raise NotImplementedError("Must supply a quote token to fetch prices for CoinGecko")
        self._ensure_data_feed()
        vs_currency = quote_token.lower()
        results = {}
        if not self._coin_gecko_supported_vs_tokens:
            while True:
                try:
                    self._coin_gecko_supported_vs_tokens = await self._coin_gecko_data_feed.get_supported_vs_tokens()
                    break
                except IOError as e:
                    # This is from exceeding the server's rate limit, signal the issue and wait for post-ban cool-off
                    self.logger().warning("Rate limit exceeded with")
                    self.logger().warning(f"   {e}\nReport to development team")
                    self.logger().warning("   Report to development team")
                    self._rate_limit_exceeded.set()
                    # This is the cool-off after a ban
                    await asyncio.sleep(COOLOFF_AFTER_BAN)
                    self.logger().info(f"   Continuing after {COOLOFF_AFTER_BAN} seconds")
                    self._rate_limit_exceeded.clear()

        if vs_currency not in self._coin_gecko_supported_vs_tokens:
            vs_currency = "usd"

        # Extra tokens: let's get them first, likely of interest to the user!
        while True:
            try:
                r = await self._get_coin_gecko_extra_token_prices(vs_currency)
                break
            except IOError as e:
                # This is from exceeding the server's rate limit, signal the issue and wait for post-ban cool-off
                self.logger().warning("Rate limit exceeded with")
                self.logger().warning(f"   {e}\nReport to development team")
                self.logger().warning("   Report to development team")
                self._rate_limit_exceeded.set()
                # This is the cool-off after a ban
                await asyncio.sleep(COOLOFF_AFTER_BAN)
                self.logger().info(f"   Continuing after {COOLOFF_AFTER_BAN} seconds")
                self._rate_limit_exceeded.clear()

        results.update(r)

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
                    self.logger().info(f"   Done with page {page_no} for {called}")
                    break
                except IOError as e:
                    # This is from exceeding the server's rate limit, signal the issue and wait for post-ban cool-off
                    self.logger().warning("Rate limit exceeded with")
                    self.logger().warning(f"   {e}\nReport to development team")
                    self.logger().warning("   Report to development team")
                    self._rate_limit_exceeded.set()
                    # This is the cool-off after a ban
                    await asyncio.sleep(COOLOFF_AFTER_BAN)
                    self.logger().info(f"   Continuing after {COOLOFF_AFTER_BAN} seconds")
                    self._rate_limit_exceeded.clear()
                except Exception:
                    self.logger().error(
                        "Unexpected error while retrieving rates from Coingecko. Check the log file for more info.")
                    raise

            # Collect the results
            for i, task_result in enumerate(task_results):
                results.update(task_result)
                filled[called[i]] = len(task_result) < 50
            # Next page calls
            page_no = page_no + 1

        self.logger().info(f"Done fetching prices from CoinGecko for {quote_token}")
        self._lock.release()
        return results

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
            while True:
                try:
                    self._coin_gecko_supported_vs_tokens = await self._coin_gecko_data_feed.get_supported_vs_tokens()
                    break
                except IOError as e:
                    # This is from exceeding the server's rate limit, signal the issue and wait for post-ban cool-off
                    self.logger().warning("Rate limit exceeded with")
                    self.logger().warning(f"   {e}\nReport to development team")
                    self.logger().warning("   Report to development team")
                    self._rate_limit_exceeded.set()
                    # This is the cool-off after a ban
                    await asyncio.sleep(COOLOFF_AFTER_BAN)
                    self.logger().info(f"   Continuing after {COOLOFF_AFTER_BAN} seconds")
                    self._rate_limit_exceeded.clear()

        if vs_currency not in self._coin_gecko_supported_vs_tokens:
            vs_currency = "usd"

        # Extra tokens: let's get them first, likely of interest to the user!
        while True:
            try:
                r = await self._get_coin_gecko_extra_token_prices(vs_currency)
                break
            except IOError as e:
                # This is from exceeding the server's rate limit, signal the issue and wait for post-ban cool-off
                self.logger().warning("Rate limit exceeded with")
                self.logger().warning(f"   {e}\nReport to development team")
                self.logger().warning("   Report to development team")
                self._rate_limit_exceeded.set()
                # This is the cool-off after a ban
                await asyncio.sleep(COOLOFF_AFTER_BAN)
                self.logger().info(f"   Continuing after {COOLOFF_AFTER_BAN} seconds")
                self._rate_limit_exceeded.clear()

        results.update(r)

        page_no: int = 1

        # Coin Gecko returns 250 assets max per page, 2500th is around 500K USD market cap (as of 2/2023)
        while page_no <= 10:
            tasks: List[Task] = []

            # The API calls could be lengthy, parallel execution, but for the same page,
            # so it detects when a category has been completed
            tasks.append(asyncio.create_task(self._get_coin_gecko_prices_by_page(vs_currency, page_no, None)))

            while True:
                try:
                    task_results = await safe_gather(*tasks, return_exceptions=False)
                    self.logger().info(
                        f"   Done with page {page_no}:{len(task_results)}")
                    break
                except IOError as e:
                    # This is from exceeding the server's rate limit, signal the issue and wait for post-ban cool-off
                    self.logger().warning("Rate limit exceeded with")
                    self.logger().warning(f"   {e}\nReport to development team")
                    self.logger().warning("   Report to development team")
                    self._rate_limit_exceeded.set()
                    # This is the cool-off after a ban
                    await asyncio.sleep(COOLOFF_AFTER_BAN)
                    self.logger().info(f"   Continuing after {COOLOFF_AFTER_BAN} seconds")
                    self._rate_limit_exceeded.clear()
                except Exception:
                    self.logger().error(
                        "Unexpected error while retrieving rates from Coingecko. Check the log file for more info.")
                    raise

            # Collect the results
            for i, task_result in enumerate(task_results):
                results.update(task_result)
            # Next page calls
            page_no = page_no + 1

        self.logger().info(f"Done fetching prices from CoinGecko for {quote_token}")
        self._lock.release()
        return results

    def _ensure_data_feed(self):
        if self._coin_gecko_data_feed is None:
            self._coin_gecko_data_feed = CoinGeckoDataFeed()

    async def _get_coin_gecko_prices_by_page(self, vs_currency: str, page_no: int, category: Union[str, None]) -> Dict[str, Decimal]:
        """
        Fetches CoinGecko prices by page number.

        :param vs_currency: A currency (crypto or fiat) to get prices of tokens in, see
        https://api.coingecko.com/api/v3/simple/supported_vs_currencies for the current supported list
        :param page_no: The page number
        :param category | None: category to filter tokens to get from the provider (specifying one limits to 50 results)

        :return: A dictionary of trading pairs and prices (50 results max if a category is provided)
        """
        results = {}
        while True:
            try:
                self.logger().info(f"Fetching price by page from CoinGecko, page {page_no}, category {category}")
                if self._rate_limit_exceeded.is_set():
                    await self._rate_limit_exceeded.wait()
                self.logger().info("   Cleared to call price by page")
                resp = await self._coin_gecko_data_feed.get_prices_by_page(
                    vs_currency=vs_currency, page_no=page_no, category=category
                )
                for record in resp:
                    pair = combine_to_hb_trading_pair(base=record['symbol'].upper(), quote=vs_currency.upper())
                    if record["current_price"]:
                        results[pair] = Decimal(str(record["current_price"]))
                return results
            except IOError as e:
                self.logger().error(f"   Exception:{e}:{category}")
                # In the rare case (hopefully) of server/client time slew
                await asyncio.sleep(self._coin_gecko_data_feed.rate_limit_retry_s)
            except Exception:
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
            self.logger().info(f"Fetching extra tokens from CoinGecko: {self._extra_token_ids}")
            if self._rate_limit_exceeded.is_set():
                await self._rate_limit_exceeded.wait()
            self.logger().info(f"   Cleared to call: {self._extra_token_ids}")
            resp = await self._coin_gecko_data_feed.get_prices_by_token_id(
                vs_currency=vs_currency, token_ids=self._extra_token_ids
            )
            for record in resp:
                pair = combine_to_hb_trading_pair(base=record["symbol"].upper(), quote=vs_currency.upper())
                if record["current_price"]:
                    results[pair] = Decimal(str(record["current_price"]))
        return results
