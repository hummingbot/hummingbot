import asyncio
import logging
from typing import (
    Dict,
    Optional,
    List
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


class RateOracle(NetworkBase):
    source: RateOracleSource = RateOracleSource.binance
    global_token: str = "USDT"
    global_token_symbol: str = "$"
    _logger: Optional[HummingbotLogger] = None
    _shared_instance: "RateOracle" = None
    _shared_client: Optional[aiohttp.ClientSession] = None
    _cgecko_supported_vs_tokens: List[str] = []

    binance_price_url = "https://api.binance.com/api/v3/ticker/bookTicker"
    coingecko_usd_price_url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency={}&order=market_cap_desc" \
                              "&per_page=250&page={}&sparkline=false"
    coingecko_supported_vs_tokens_url = "https://api.coingecko.com/api/v3/simple/supported_vs_currencies"

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

    def update_interval(self) -> float:
        return 1.0

    def rate(self, pair: str) -> Decimal:
        return find_rate(self._prices, pair)

    @classmethod
    async def rate_async(cls, pair: str) -> Decimal:
        prices = await cls.get_prices()
        return find_rate(prices, pair)

    @classmethod
    async def global_rate(cls, token: str) -> Decimal:
        prices = await cls.get_prices()
        pair = token + "-" + cls.global_token
        return find_rate(prices, pair)

    @classmethod
    async def global_value(cls, token: str, amount: Decimal) -> Decimal:
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
            await asyncio.sleep(self.update_interval())

    @classmethod
    async def get_prices(cls) -> Dict[str, Decimal]:
        if cls.source == RateOracleSource.binance:
            return await cls.get_binance_prices()
        elif cls.source == RateOracleSource.coingecko:
            return await cls.get_coingecko_prices(cls.global_token)
        else:
            raise NotImplementedError

    @classmethod
    @async_ttl_cache(ttl=1, maxsize=1)
    async def get_binance_prices(cls) -> Dict[str, Decimal]:
        results = {}
        client = await cls._http_client()
        try:
            async with client.request("GET", cls.binance_price_url) as resp:
                records = await resp.json()
                for record in records:
                    trading_pair = binance_convert_from_exchange_pair(record["symbol"])
                    if trading_pair and record["bidPrice"] is not None and record["askPrice"] is not None:
                        results[trading_pair] = (Decimal(record["bidPrice"]) + Decimal(record["askPrice"])) / Decimal("2")
        except asyncio.CancelledError:
            raise
        except Exception:
            cls.logger().error("Unexpected error while retrieving rates from Binance.")
        return results

    @classmethod
    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_coingecko_prices(cls, vs_currency: str) -> Dict[str, Decimal]:
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
        results = {}
        client = await cls._http_client()
        async with client.request("GET", cls.coingecko_usd_price_url.format(vs_currency, page_no)) as resp:
            records = await resp.json()
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
