import asyncio
import logging

from decimal import Decimal
from enum import Enum
from typing import (
    Dict,
    List,
    Optional,
)

import aiohttp

import hummingbot.client.settings # noqa
from hummingbot.connector.exchange.ascend_ex.ascend_ex_utils import convert_from_exchange_trading_pair as \
    ascend_ex_convert_from_exchange_pair
from hummingbot.connector.exchange.binance.binance_api_order_book_data_source import BinanceAPIOrderBookDataSource
from hummingbot.connector.exchange.kucoin.kucoin_utils import convert_from_exchange_trading_pair as \
    kucoin_convert_from_exchange_pair
from hummingbot.core.network_base import NetworkBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.rate_oracle.utils import find_rate
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger


class RateOracleSource(Enum):
    """
    Supported sources for RateOracle
    """
    binance = 0
    coingecko = 1
    kucoin = 2
    ascend_ex = 3


class RateOracle(NetworkBase):
    """
    RateOracle provides conversion rates for any given pair token symbols in both async and sync fashions.
    It achieves this by query URL on a given source for prices and store them, either in cache or as an object member.
    The find_rate is then used on these prices to find a rate on a given pair.
    """
    # Set these below class members before query for rates
    source: RateOracleSource = RateOracleSource.binance
    global_token: str = "USDT"
    global_token_symbol: str = "$"

    _logger: Optional[HummingbotLogger] = None
    _shared_instance: "RateOracle" = None
    _shared_client: Optional[aiohttp.ClientSession] = None
    _cgecko_supported_vs_tokens: List[str] = []

    binance_price_url = "https://api.binance.com/api/v3/ticker/bookTicker"
    binance_us_price_url = "https://api.binance.us/api/v3/ticker/bookTicker"
    coingecko_usd_price_url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency={}&order=market_cap_desc" \
                              "&per_page=250&page={}&sparkline=false"
    coingecko_supported_vs_tokens_url = "https://api.coingecko.com/api/v3/simple/supported_vs_currencies"
    kucoin_price_url = "https://api.kucoin.com/api/v1/market/allTickers"
    ascend_ex_price_url = "https://ascendex.com/api/pro/v1/ticker"

    @classmethod
    def get_instance(cls) -> "RateOracle":
        if cls._shared_instance is None:
            cls._shared_instance = RateOracle()
        return cls._shared_instance

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self):
        super().__init__()
        self._check_network_interval = 30.0
        self._ev_loop = asyncio.get_event_loop()
        self._prices: Dict[str, Decimal] = {}
        self._fetch_price_task: Optional[asyncio.Task] = None
        self._ready_event = asyncio.Event()

    def __str__(self):
        return f"{self.source.name.title()} rate oracle"

    @classmethod
    async def _http_client(cls) -> aiohttp.ClientSession:
        if cls._shared_client is None:
            cls._shared_client = aiohttp.ClientSession()
        return cls._shared_client

    async def get_ready(self):
        """
        The network is ready when it first successfully get prices for a given source.
        """
        try:
            if not self._ready_event.is_set():
                await self._ready_event.wait()
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error while waiting for data feed to get ready.",
                                exc_info=True)

    @property
    def name(self) -> str:
        return "rate_oracle"

    @property
    def prices(self) -> Dict[str, Decimal]:
        """
        Actual prices retrieved from URL
        """
        return self._prices.copy()

    def rate(self, pair: str) -> Decimal:
        """
        Finds a conversion rate for a given symbol, this can be direct or indirect prices as long as it can find a route
        to achieve this.
        :param pair: A trading pair, e.g. BTC-USDT
        :return A conversion rate
        """
        return find_rate(self._prices, pair)

    @classmethod
    async def rate_async(cls, pair: str) -> Decimal:
        """
        Finds a conversion rate in an async operation, it is a class method which can be used directly without having to
        start the RateOracle network.
        :param pair: A trading pair, e.g. BTC-USDT
        :return A conversion rate
        """
        prices = await cls.get_prices()
        return find_rate(prices, pair)

    @classmethod
    async def global_rate(cls, token: str) -> Decimal:
        """
        Finds a conversion rate of a given token to a global token
        :param token: A token symbol, e.g. BTC
        :return A conversion rate
        """
        prices = await cls.get_prices()
        pair = token + "-" + cls.global_token
        return find_rate(prices, pair)

    @classmethod
    async def global_value(cls, token: str, amount: Decimal) -> Decimal:
        """
        Finds a value of a given token amount in a global token unit
        :param token: A token symbol, e.g. BTC
        :param amount: An amount of token to be converted to value
        :return A value of the token in global token unit
        """
        rate = await cls.global_rate(token)
        rate = Decimal("0") if rate is None else rate
        return amount * rate

    async def fetch_price_loop(self):
        while True:
            try:
                self._prices = await self.get_prices()
                if self._prices:
                    self._ready_event.set()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(f"Error fetching new prices from {self.source.name}.", exc_info=True,
                                      app_warning_msg=f"Couldn't fetch newest prices from {self.source.name}.")
            await asyncio.sleep(1)

    @classmethod
    async def get_prices(cls) -> Dict[str, Decimal]:
        """
        Fetches prices of a specified source
        :return A dictionary of trading pairs and prices
        """
        if cls.source == RateOracleSource.binance:
            return await cls.get_binance_prices()
        elif cls.source == RateOracleSource.coingecko:
            return await cls.get_coingecko_prices(cls.global_token)
        elif cls.source == RateOracleSource.kucoin:
            return await cls.get_kucoin_prices()
        elif cls.source == RateOracleSource.ascend_ex:
            return await cls.get_ascend_ex_prices()
        else:
            raise NotImplementedError

    @classmethod
    @async_ttl_cache(ttl=1, maxsize=1)
    async def get_binance_prices(cls) -> Dict[str, Decimal]:
        """
        Fetches Binance prices from binance.com and binance.us where only USD pairs from binance.us prices are added
        to the prices dictionary.
        :return A dictionary of trading pairs and prices
        """
        results = {}
        tasks = [cls.get_binance_prices_by_domain(cls.binance_price_url),
                 cls.get_binance_prices_by_domain(cls.binance_us_price_url, "USD", domain="us")]
        task_results = await safe_gather(*tasks, return_exceptions=True)
        for task_result in task_results:
            if isinstance(task_result, Exception):
                cls.logger().error("Unexpected error while retrieving rates from Binance. "
                                   "Check the log file for more info.")
                break
            else:
                results.update(task_result)
        return results

    @classmethod
    async def get_binance_prices_by_domain(cls,
                                           url: str,
                                           quote_symbol: str = None,
                                           domain: str = "com") -> Dict[str, Decimal]:
        """
        Fetches binance prices
        :param url: A URL end point
        :param quote_symbol: A quote symbol, if specified only pairs with the quote symbol are included for prices
        :param domain: The Binance domain to query. It could be 'com' or 'us'
        :return: A dictionary of trading pairs and prices
        """
        results = {}
        client = await cls._http_client()
        async with client.request("GET", url) as resp:
            records = await resp.json()
            for record in records:
                try:
                    trading_pair = await BinanceAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
                        record["symbol"], domain=domain)
                except KeyError:
                    # Ignore results for which their symbols is not tracked by the Binance connector
                    continue
                if quote_symbol is not None:
                    base, quote = trading_pair.split("-")
                    if quote != quote_symbol:
                        continue
                if (trading_pair and record["bidPrice"] is not None
                        and record["askPrice"] is not None
                        and Decimal(record["bidPrice"]) > 0
                        and Decimal(record["askPrice"])):
                    results[trading_pair] = ((Decimal(record["bidPrice"]) + Decimal(record["askPrice"]))
                                             / Decimal("2"))

        return results

    @classmethod
    @async_ttl_cache(ttl=1, maxsize=1)
    async def get_kucoin_prices(cls) -> Dict[str, Decimal]:
        """
        Fetches Kucoin mid prices from their allTickers endpoint.
        :return A dictionary of trading pairs and prices
        """
        results = {}
        client = await cls._http_client()
        async with client.request("GET", cls.kucoin_price_url) as resp:
            records = await resp.json(content_type=None)
            for record in records["data"]["ticker"]:
                pair = kucoin_convert_from_exchange_pair(record["symbolName"])
                if Decimal(record["buy"]) > 0 and Decimal(record["sell"]) > 0:
                    results[pair] = (Decimal(str(record["buy"])) + Decimal(str(record["sell"]))) / Decimal("2")
        return results

    @classmethod
    @async_ttl_cache(ttl=1, maxsize=1)
    async def get_ascend_ex_prices(cls) -> Dict[str, Decimal]:
        """
        Fetches Ascend Ex mid prices from their ticker endpoint.
        :return A dictionary of trading pairs and prices
        """
        results = {}
        client = await cls._http_client()
        async with client.request("GET", cls.ascend_ex_price_url) as resp:
            records = await resp.json(content_type=None)
            for record in records["data"]:
                pair = ascend_ex_convert_from_exchange_pair(record["symbol"])
                if Decimal(record["ask"][0]) > 0 and Decimal(record["bid"][0]) > 0:
                    results[pair] = (Decimal(str(record["ask"][0])) + Decimal(str(record["bid"][0]))) / Decimal("2")
        return results

    @classmethod
    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_coingecko_prices(cls, vs_currency: str) -> Dict[str, Decimal]:
        """
        Fetches CoinGecko prices for the top 1000 token (order by market cap), each API query returns 250 results,
        hence it queries 4 times concurrently.
        :param vs_currency: A currency (crypto or fiat) to get prices of tokens in, see
        https://api.coingecko.com/api/v3/simple/supported_vs_currencies for the current supported list
        :return A dictionary of trading pairs and prices
        """
        results = {}
        if not cls._cgecko_supported_vs_tokens:
            client = await cls._http_client()
            async with client.request("GET", cls.coingecko_supported_vs_tokens_url) as resp:
                records = await resp.json()
                cls._cgecko_supported_vs_tokens = records
        if vs_currency.lower() not in cls._cgecko_supported_vs_tokens:
            vs_currency = "usd"
        tasks = [cls.get_coingecko_prices_by_page(vs_currency, i) for i in range(1, 5)]
        task_results = await safe_gather(*tasks, return_exceptions=True)
        for task_result in task_results:
            if isinstance(task_result, Exception):
                cls.logger().error("Unexpected error while retrieving rates from Coingecko. "
                                   "Check the log file for more info.")
                break
            else:
                results.update(task_result)
        return results

    @classmethod
    async def get_coingecko_prices_by_page(cls, vs_currency: str, page_no: int) -> Dict[str, Decimal]:
        """
        Fetches CoinGecko prices by page number.
        :param vs_currency: A currency (crypto or fiat) to get prices of tokens in, see
        https://api.coingecko.com/api/v3/simple/supported_vs_currencies for the current supported list
        :param page_no: The page number
        :return A dictionary of trading pairs and prices (250 results max)
        """
        results = {}
        client = await cls._http_client()
        async with client.request("GET", cls.coingecko_usd_price_url.format(vs_currency, page_no)) as resp:
            records = await resp.json(content_type=None)
            for record in records:
                pair = f'{record["symbol"].upper()}-{vs_currency.upper()}'
                if record["current_price"]:
                    results[pair] = Decimal(str(record["current_price"]))
        return results

    async def start_network(self):
        await self.stop_network()
        self._fetch_price_task = safe_ensure_future(self.fetch_price_loop())

    async def stop_network(self):
        if self._fetch_price_task is not None:
            self._fetch_price_task.cancel()
            self._fetch_price_task = None

    async def check_network(self) -> NetworkStatus:
        try:
            prices = await self.get_prices()
            if not prices:
                raise Exception(f"Error fetching new prices from {self.source.name}.")
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def start(self):
        NetworkBase.start(self)

    def stop(self):
        NetworkBase.stop(self)
