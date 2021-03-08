import asyncio
import logging
from typing import (
    Dict,
    Optional,
)
from decimal import Decimal
import aiohttp
from enum import Enum
from hummingbot.logger import HummingbotLogger
from hummingbot.core.network_base import NetworkBase, NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.connector.exchange.binance.binance_utils import convert_from_exchange_trading_pair as \
    binance_convert_from_exchange_pair
from hummingbot.core.rate_oracle.utils import find_rate
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils import async_ttl_cache


class RateOracleSource(Enum):
    binance = 0
    coingecko = 1
    kucoin = 2


class RateOracle(NetworkBase):
    _logger: Optional[HummingbotLogger] = None
    _shared_instance: "RateOracle" = None
    _shared_client: Optional[aiohttp.ClientSession] = None

    binance_price_url = "https://api.binance.com/api/v3/ticker/bookTicker"
    coingecko_usd_price_url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc" \
                              "&per_page=250&page={}&sparkline=false"

    @classmethod
    def get_instance(cls, source: RateOracleSource) -> "RateOracle":
        if cls._shared_instance is None:
            cls._shared_instance = RateOracle(source)
        elif cls._shared_instance.source != source:
            cls._shared_instance.stop()
            cls._shared_instance = RateOracle(source)
        return cls._shared_instance

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, source: RateOracleSource):
        super().__init__()
        self._check_network_interval = 30.0
        self._ev_loop = asyncio.get_event_loop()
        self._source = source
        self._prices: Dict[str, Decimal] = {}
        self._fetch_price_task: Optional[asyncio.Task] = None
        self._ready_event = asyncio.Event()

    @classmethod
    async def _http_client(cls) -> aiohttp.ClientSession:
        if cls._shared_client is None:
            cls._shared_client = aiohttp.ClientSession()
        return cls._shared_client

    async def get_ready(self):
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
        return self._prices.copy()

    @property
    def source(self) -> RateOracleSource:
        return self._source

    def update_interval(self) -> float:
        if self._source == RateOracleSource.binance:
            return 1.0
        return 30.0

    def get_rate(self, pair: str) -> float:
        return find_rate(self._prices, pair)

    @classmethod
    async def get_rate_from_source(cls, source: RateOracleSource, pair: str) -> Dict[str, Decimal]:
        prices = await cls.get_prices(source)
        return find_rate(prices, pair)

    async def fetch_price_loop(self):
        while True:
            try:
                self._prices = await self.get_prices(self._source)
                if self._prices:
                    self._ready_event.set()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(f"Error fetching new prices from {self._source.name}.", exc_info=True,
                                      app_warning_msg=f"Couldn't fetch newest prices from {self._source.name}.")
            await asyncio.sleep(self.update_interval())

    @classmethod
    async def get_prices(cls, source: RateOracleSource) -> Dict[str, Decimal]:
        if source == RateOracleSource.binance:
            return await cls.get_binance_prices()
        elif source == RateOracleSource.coingecko:
            return await cls.get_coingecko_prices()

    @classmethod
    @async_ttl_cache(ttl=1, maxsize=1)
    async def get_binance_prices(cls) -> Dict[str, Decimal]:
        results = {}
        client = await cls._http_client()
        async with client.request("GET", cls.binance_price_url) as resp:
            records = await resp.json()
            for record in records:
                trading_pair = binance_convert_from_exchange_pair(record["symbol"])
                if trading_pair and record["bidPrice"] is not None and record["askPrice"] is not None:
                    results[trading_pair] = (Decimal(record["bidPrice"]) + Decimal(record["askPrice"])) / Decimal("2")
        return results

    @classmethod
    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_coingecko_prices(cls) -> Dict[str, Decimal]:
        print("getting coingecko prices")
        results = {}
        tasks = [cls.get_coingecko_prices_by_page(i) for i in range(1, 5)]
        task_results = await safe_gather(*tasks, return_exceptions=True)
        for task_result in task_results:
            results.update(task_result)
        return results

    @classmethod
    async def get_coingecko_prices_by_page(cls, page_no: int) -> Dict[str, Decimal]:
        results = {}
        client = await cls._http_client()
        async with client.request("GET", cls.coingecko_usd_price_url.format(page_no)) as resp:
            records = await resp.json()
            for record in records:
                pair = record["symbol"].upper() + "-USD"
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
            prices = await self.get_prices(self._source)
            if not prices:
                raise Exception(f"Error fetching new prices from {self._source.name}.")
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def start(self):
        NetworkBase.start(self)

    def stop(self):
        NetworkBase.stop(self)
